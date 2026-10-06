import ast
import operator
import sqlite3
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests from the frontend

DB = 'calculator.db'

# Allowed operators
ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def init_db():
    with sqlite3.connect(DB) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expression TEXT NOT NULL,
                result TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')


init_db()


def eval_expr(node):
    """Safely evaluate an AST node recursively."""
    if isinstance(node, ast.Expression):
        return eval_expr(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            raise ValueError('Boolean values are not supported')
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError('Only numbers are supported')

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in ALLOWED_OPS:
            raise ValueError('Unsupported operator')
        left = eval_expr(node.left)
        right = eval_expr(node.right)
        if op_type is ast.Div and right == 0:
            raise ZeroDivisionError('Division by zero')
        return ALLOWED_OPS[op_type](left, right)

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in ALLOWED_OPS:
            raise ValueError('Unsupported unary operator')
        return ALLOWED_OPS[op_type](eval_expr(node.operand))

    raise ValueError('Invalid expression')


def safe_calc(expression: str):
    """Parse and evaluate an expression without using eval()."""
    tree = ast.parse(expression, mode='eval')
    return eval_expr(tree)


@app.route('/api/calculate', methods=['POST'])
def calculate():
    data = request.get_json(silent=True) or {}
    expression = (data.get('expression') or '').strip()

    if not expression:
        return jsonify({'success': False, 'error': 'Expression cannot be empty'}), 400

    try:
        result = safe_calc(expression)
        # Display integers without decimal point
        if isinstance(result, float) and result.is_integer():
            result_str = str(int(result))
        else:
            result_str = str(result)

        created_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with sqlite3.connect(DB) as conn:
            cur = conn.execute(
                'INSERT INTO history (expression, result, created_at) VALUES (?, ?, ?)',
                (expression, result_str, created_at)
            )
            record_id = cur.lastrowid

        return jsonify({
            'success': True,
            'id': record_id,
            'expression': expression,
            'result': result_str,
            'created_at': created_at
        })
    except ZeroDivisionError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception:
        return jsonify({'success': False, 'error': 'Invalid expression'}), 400


@app.route('/api/history', methods=['GET'])
def get_history():
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            'SELECT id, expression, result, created_at FROM history ORDER BY id DESC'
        ).fetchall()
        return jsonify([dict(row) for row in rows])


@app.route('/api/history/<int:record_id>', methods=['DELETE'])
def delete_history(record_id):
    with sqlite3.connect(DB) as conn:
        cur = conn.execute('DELETE FROM history WHERE id = ?', (record_id,))
        if cur.rowcount == 0:
            return jsonify({'success': False, 'error': 'Record not found'}), 404
    return jsonify({'success': True})


if __name__ == '__main__':
    app.run(debug=True, port=5000)