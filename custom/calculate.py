"""Calculator plugin — evaluate a math expression safely."""

from openjarvis.plugins import plugin


@plugin("calculate")
def calculate(jarvis, s):
    """Calculate a math expression. Usage: calculate 2 + 2 * 10"""
    if not s.strip():
        jarvis.say("Usage: calculate <expression>  e.g. calculate 2 + 2")
        return
    try:
        # Safe eval: only allow math operations
        import ast, operator
        _OPS = {
            ast.Add: operator.add, ast.Sub: operator.sub,
            ast.Mult: operator.mul, ast.Div: operator.truediv,
            ast.Pow: operator.pow, ast.Mod: operator.mod,
            ast.UAdd: operator.pos, ast.USub: operator.neg,
        }

        def _eval(node):
            if isinstance(node, ast.Constant):
                return node.value
            if isinstance(node, ast.BinOp):
                return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
            if isinstance(node, ast.UnaryOp):
                return _OPS[type(node.op)](_eval(node.operand))
            raise ValueError(f"Unsupported operation: {ast.dump(node)}")

        tree = ast.parse(s.strip(), mode="eval")
        result = _eval(tree.body)
        jarvis.say(f"{s.strip()} = {result}")
    except Exception as exc:
        jarvis.say(f"Could not calculate: {exc}")
