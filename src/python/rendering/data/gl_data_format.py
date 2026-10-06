import struct
from dataclasses import dataclass
from enum import Enum, auto

from rendering.data.gl_types import component_count, zero_of, GL_TYPES, align_offset


class MemoryLayout(Enum):
    PACKED = auto()
    STD140 = auto()
    STD430 = auto()


@dataclass(frozen=True)
class GlDataAttribute:
    name: str
    type: type
    default: object | None = None
    array_size: int | None = None

    @property
    def size(self):
        return component_count(self.type)


class GlDataRecord:
    def __init__(self, **attributes):
        self.__dict__.update(attributes)

    def get_value(self, attribute):
        value = getattr(self, attribute.name, None)

        if value is not None:
            return value

        if attribute.default is not None:
            return attribute.default if attribute.array_size else attribute.type(attribute.default)

        if attribute.array_size:
            return [zero_of(attribute.type) for _ in range(attribute.array_size)]

        return zero_of(attribute.type)


Vertex = GlDataRecord
Instance = GlDataRecord


class GlDataFormat:
    def __init__(self, layout: MemoryLayout, *attributes: GlDataAttribute):
        self.layout = layout
        self.attributes = attributes
        self.stride_bytes = 0

        self._attributes_by_name = {}
        self._offsets = {}
        self._field_serializers = {}
        self._serialization_plan = []  # List of compiled steps: (attr_name, offset, serializer, default_bytes)

        self._compile_layout()

    def _compile_layout(self):
        current_offset = 0
        max_alignment = 0

        for attr in self.attributes:
            self._attributes_by_name[attr.name] = attr
            info = GL_TYPES[attr.type]
            alignment = info.align_140 if self.layout == MemoryLayout.STD140 else info.align_430

            # STD140 aligns arrays and their elements to a vec4 (16 bytes) minimum
            if attr.array_size and self.layout == MemoryLayout.STD140:
                alignment = max(alignment, 16)

            if self.layout == MemoryLayout.PACKED:
                alignment = 1

            max_alignment = max(max_alignment, alignment)
            current_offset = align_offset(current_offset, alignment)

            self._offsets[attr.name] = current_offset

            if attr.type is float:
                base_serializer = lambda v: struct.pack("f", float(v))
            elif attr.type in (int, bool):
                base_serializer = lambda v: struct.pack("i", int(v))
            elif info.is_matrix and self.layout != MemoryLayout.PACKED:
                col_info = GL_TYPES[info.col_type]
                col_align = col_info.align_140 if self.layout == MemoryLayout.STD140 else col_info.align_430
                col_stride = align_offset(col_info.size_bytes,
                                          max(16, col_align) if self.layout == MemoryLayout.STD140 else col_align)

                def make_matrix_serializer(stride, cols, col_size):
                    def matrix_serializer(v):
                        mat_bytes = bytearray(stride * cols)
                        for i in range(cols):
                            start = i * stride
                            col_val = v[i] if not hasattr(v, 'to_list') else v[i]
                            mat_bytes[start: start + col_size] = col_val.tobytes() if hasattr(col_val,
                                                                                              'tobytes') else bytes(
                                col_val)
                        return bytes(mat_bytes)

                    return matrix_serializer

                base_serializer = make_matrix_serializer(col_stride, info.cols, col_info.size_bytes)
            else:
                base_serializer = lambda v: v.tobytes() if hasattr(v, 'tobytes') else bytes(v)

            if attr.array_size:
                base_element_size = (col_stride * info.cols) if (
                            info.is_matrix and self.layout != MemoryLayout.PACKED) else info.size_bytes
                element_stride = base_element_size

                if self.layout == MemoryLayout.STD140:
                    element_stride = align_offset(base_element_size, 16)
                elif self.layout == MemoryLayout.STD430:
                    element_stride = align_offset(base_element_size, info.align_430)

                def make_array_serializer(b_serializer, arr_size, elem_stride):
                    def array_serializer(v):
                        arr_bytes = bytearray(elem_stride * arr_size)
                        if v is None: return bytes(arr_bytes)
                        for i in range(min(arr_size, len(v))):
                            start = i * elem_stride
                            item_bytes = b_serializer(v[i])
                            arr_bytes[start: start + len(item_bytes)] = item_bytes
                        return bytes(arr_bytes)

                    return array_serializer

                serializer = make_array_serializer(base_serializer, attr.array_size, element_stride)
                attr_size_bytes = element_stride * attr.array_size
            else:
                serializer = base_serializer
                attr_size_bytes = (col_stride * info.cols) if (
                            info.is_matrix and self.layout != MemoryLayout.PACKED) else info.size_bytes

            self._field_serializers[attr.name] = serializer

            if attr.array_size:
                def_val = attr.default if attr.default is not None else [zero_of(attr.type) for _ in
                                                                         range(attr.array_size)]
            else:
                def_val = attr.type(attr.default) if attr.default is not None else zero_of(attr.type)

            default_bytes = serializer(def_val)

            self._serialization_plan.append((attr.name, current_offset, serializer, default_bytes))
            current_offset += attr_size_bytes

        self.stride_bytes = align_offset(current_offset,
                                         max_alignment) if self.layout != MemoryLayout.PACKED else current_offset

    def get_attribute(self, name: str) -> GlDataAttribute | None:
        return self._attributes_by_name.get(name)

    def offset_bytes(self, name: str) -> int:
        return self._offsets[name]

    def serialize_field(self, name: str, value) -> bytes:
        return self._field_serializers[name](value)

    def serialize(self, record: GlDataRecord) -> bytes:
        data = bytearray(self.stride_bytes)
        for attr_name, offset, serializer, default_bytes in self._serialization_plan:
            val = getattr(record, attr_name, None)
            raw = serializer(val) if val is not None else default_bytes
            data[offset: offset + len(raw)] = raw
        return bytes(data)


class VertexFormat(GlDataFormat):
    def __init__(self, *attributes: GlDataAttribute):
        super().__init__(MemoryLayout.PACKED, *attributes)


class ShaderBufferFormat(GlDataFormat):
    def __init__(self, *attributes: GlDataAttribute):
        super().__init__(MemoryLayout.STD430, *attributes)


class UniformBufferFormat(GlDataFormat):
    def __init__(self, *attributes: GlDataAttribute):
        super().__init__(MemoryLayout.STD140, *attributes)
