from .base_monitor import BaseMonitor


class SketchMonitor(BaseMonitor):
    def __init__(self, sketch_tool):
        """
        Initialize with a reference to the SketchTool instance.
        
        Args:
            sketch_tool: Instance of the SketchTool class
        """
        self.sketch_tool = sketch_tool

    def get_raw_data(self) -> str:
        """
        Retrieve the current content from the sketchpad.
        
        Returns:
            String content of the sketchpad
        """
        return self.sketch_tool.sketchpad_get_content()

    def render(self) -> str:
        """
        Render the sketchpad content in XML format.
        Skip rendering if there's no content to display.
        
        Returns:
            XML representation of the sketchpad content or empty string if no content
        """
        content = self.get_raw_data()
        if not content:
            return ""

        return self.wrap_in_xml(
            "sketchpad_content",
            f"\n{content}\n",
            {"source": "sketchpad"}
        )
