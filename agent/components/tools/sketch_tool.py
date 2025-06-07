class SketchTool:
    def __init__(self):
        self.content = ""

    def sketchpad_append(self, text: str):
        """Adds new text to the end of the existing content."""
        self.content += f'\n{text}'
        return "Text was successfully added to sketchpad!"
    
    def sketchpad_replace(self, text_old: str, text_new: str) -> bool:
        """Replaces all occurrences of a specified text with new text in the sketchpad content."""
        self.content.replace(text_old, text_new)
        return 'All occurences in the sketchpad were replaced!'
    
    def sketchpad_clear(self):
        """Removes all content from the sketchpad, resetting it to an empty string."""
        self.content = ""
        return 'Sketchpad was successfully cleared!'
    
    def sketchpad_get_content(self) -> str:
        """Returns the current sketchpad content."""
        return self.content
