from model.composite_structure import CompositeStructure
from util.power_util import build_composite_entities, create_picture_composite_structure
from util.startup import checkpoint


class PowerModelsRepository:
    composite_structures: dict[str, list[CompositeStructure]] = dict()
    def __init__(self, plant_types):
        self.plant_types: list[str] = plant_types



    def fill_empty_composite_structures(self, cull_shader):
        for plant_type in self.plant_types:
            if not self.composite_structures.get(plant_type):
                self.composite_structures[plant_type] = create_picture_composite_structure(plant_type, cull_shader)
            checkpoint()

    def update_plant_models(self, plants):
        for structure_list in self.composite_structures.values():
            for structure in structure_list:
                structure.model.entities.clear()
            checkpoint()

        build_composite_entities(plants, self.composite_structures)

        for structure_list in self.composite_structures.values():
            for structure in structure_list:
                structure.model.upload_instances()
            checkpoint()
