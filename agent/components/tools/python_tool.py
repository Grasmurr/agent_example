from multiprocessing import Manager


class PythonTool:
    def __init__(self):
        pass
    
    def eval_python(self, python_code: str) -> str:
        """
        Evaluates a Python expression.
        Нужно для вычислений
        """
        try:
            result = eval(python_code)
            return str(result)
        except Exception as e:
            return f'Error: {e}'
    
    def exec_python(self, python_code: str) -> str:
        """
        Executes a Python expression.
        Нужно для выполнения питон кода
        """

        try:
            manager = Manager()
            memory = manager.dict()
            exec(python_code, globals(), memory)
            return str(memory)
        except Exception as e:
            return f'Error: {e}'