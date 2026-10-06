import re

class ShaderPreprocessingError(RuntimeError):
    def __init__(self, msg: str):
        super().__init__(
            f"Shader program preprocessing failed:\n{msg.strip()}"
        )

class ShaderCompilationError(RuntimeError):
    def __init__(self,
                 filename: str,
                 shader_type: str,
                 source: str,
                 log: str,
                 context_lines: int = 3):
        lines = source.splitlines()

        snippets = []

        line_no = "unknown"
        for match in re.finditer(r"\((\d+)\)", log):
            line_no = int(match.group(1))

            start = max(1, line_no - context_lines)
            end = min(len(lines), line_no + context_lines)

            snippet = "\n".join(
                f"{i:>4} {'>>' if i == line_no else '  '} {lines[i - 1]}"
                for i in range(start, end + 1)
            )

            snippets.append(snippet)

        snippet_text = "\n\n".join(snippets) if snippets else "<unable to locate line>"

        super().__init__(
            f"\n\nShader compilation failed\n"
            f'File "{filename}", line {line_no}\n'
            f"Type: {shader_type}\n\n"
            f"Compiler output:\n"
            f"{log.strip()}\n\n"
            f"Source context:\n"
            f"{snippet_text}"
        )

class ShaderLinkingError(RuntimeError):
    def __init__(self, log: str):
        super().__init__(
            f"Shader program linking failed\n"
            f"Linker output:\n{log.strip()}"
        )
