import java.util.*;
import java.util.stream.*;

// ==================== CORE INTERFACES ====================

interface Expression {
    Object interpret(Context context);
}

interface BooleanExpr {
    boolean interpret(Context context);
}

interface NumericExpr {
    double interpret(Context context);
}

// ==================== CONTEXT ====================

class Context {
    private Map<String, Object> variables = new HashMap<>();

    public void setVariable(String name, Object value) {
        variables.put(name, value);
    }

    public Object getVariable(String name) {
        return variables.get(name);
    }

    public double getNumber(String name) {
        Object val = variables.get(name);
        if (val instanceof Number) return ((Number) val).doubleValue();
        throw new RuntimeException("Variable '" + name + "' is not a number");
    }

    public boolean getBoolean(String name) {
        Object val = variables.get(name);
        if (val instanceof Boolean) return (Boolean) val;
        throw new RuntimeException("Variable '" + name + "' is not a boolean");
    }

    @Override
    public String toString() {
        return "Context" + variables;
    }
}

// ==================== TERMINAL EXPRESSIONS ====================

class NumberExpression implements NumericExpr {
    private double value;

    public NumberExpression(double value) {
        this.value = value;
    }

    @Override
    public double interpret(Context context) {
        return value;
    }

    @Override
    public String toString() {
        return String.valueOf(value);
    }
}

class VariableExpression implements NumericExpr {
    private String name;

    public VariableExpression(String name) {
        this.name = name;
    }

    @Override
    public double interpret(Context context) {
        return context.getNumber(name);
    }

    @Override
    public String toString() {
        return name;
    }
}

class BooleanExpression implements BooleanExpr {
    private boolean value;

    public BooleanExpression(boolean value) {
        this.value = value;
    }

    @Override
    public boolean interpret(Context context) {
        return value;
    }

    @Override
    public String toString() {
        return String.valueOf(value);
    }
}

class BooleanVariableExpression implements BooleanExpr {
    private String name;

    public BooleanVariableExpression(String name) {
        this.name = name;
    }

    @Override
    public boolean interpret(Context context) {
        return context.getBoolean(name);
    }

    @Override
    public String toString() {
        return name;
    }
}

// ==================== NON-TERMINAL NUMERIC EXPRESSIONS ====================

class AddExpression implements NumericExpr {
    private NumericExpr left, right;

    public AddExpression(NumericExpr left, NumericExpr right) {
        this.left = left;
        this.right = right;
    }

    @Override
    public double interpret(Context context) {
        return left.interpret(context) + right.interpret(context);
    }

    @Override
    public String toString() {
        return "(" + left + " + " + right + ")";
    }
}

class SubtractExpression implements NumericExpr {
    private NumericExpr left, right;

    public SubtractExpression(NumericExpr left, NumericExpr right) {
        this.left = left;
        this.right = right;
    }

    @Override
    public double interpret(Context context) {
        return left.interpret(context) - right.interpret(context);
    }

    @Override
    public String toString() {
        return "(" + left + " - " + right + ")";
    }
}

class MultiplyExpression implements NumericExpr {
    private NumericExpr left, right;

    public MultiplyExpression(NumericExpr left, NumericExpr right) {
        this.left = left;
        this.right = right;
    }

    @Override
    public double interpret(Context context) {
        return left.interpret(context) * right.interpret(context);
    }

    @Override
    public String toString() {
        return "(" + left + " * " + right + ")";
    }
}

// ==================== NON-TERMINAL BOOLEAN EXPRESSIONS ====================

class AndExpression implements BooleanExpr {
    private BooleanExpr left, right;

    public AndExpression(BooleanExpr left, BooleanExpr right) {
        this.left = left;
        this.right = right;
    }

    @Override
    public boolean interpret(Context context) {
        return left.interpret(context) && right.interpret(context);
    }

    @Override
    public String toString() {
        return "(" + left + " AND " + right + ")";
    }
}

class OrExpression implements BooleanExpr {
    private BooleanExpr left, right;

    public OrExpression(BooleanExpr left, BooleanExpr right) {
        this.left = left;
        this.right = right;
    }

    @Override
    public boolean interpret(Context context) {
        return left.interpret(context) || right.interpret(context);
    }

    @Override
    public String toString() {
        return "(" + left + " OR " + right + ")";
    }
}

class GreaterThanExpression implements BooleanExpr {
    private NumericExpr left, right;

    public GreaterThanExpression(NumericExpr left, NumericExpr right) {
        this.left = left;
        this.right = right;
    }

    @Override
    public boolean interpret(Context context) {
        return left.interpret(context) > right.interpret(context);
    }

    @Override
    public String toString() {
        return "(" + left + " > " + right + ")";
    }
}

class EqualExpression implements BooleanExpr {
    private String variable;
    private Object expectedValue;

    public EqualExpression(String variable, Object expectedValue) {
        this.variable = variable;
        this.expectedValue = expectedValue;
    }

    @Override
    public boolean interpret(Context context) {
        Object actual = context.getVariable(variable);
        return expectedValue.equals(actual);
    }

    @Override
    public String toString() {
        return "(" + variable + " = " + expectedValue + ")";
    }
}

// ==================== SQL-LIKE QUERY INTERPRETER ====================

class SqlQuery {
    private String table;
    private List<String> columns;
    private BooleanExpr whereClause;

    public SqlQuery(List<String> columns, String table, BooleanExpr whereClause) {
        this.columns = columns;
        this.table = table;
        this.whereClause = whereClause;
    }

    public boolean matches(Context rowContext) {
        return whereClause.interpret(rowContext);
    }

    public String getTable() { return table; }
    public List<String> getColumns() { return columns; }

    @Override
    public String toString() {
        String cols = columns.contains("*") ? "*" : String.join(", ", columns);
        return "SELECT " + cols + " FROM " + table + " WHERE " + whereClause;
    }
}

class SqlParser {
    // Parses: "SELECT * FROM users WHERE age > 25 AND active = true"
    public static SqlQuery parse(String sql) {
        String[] parts = sql.split("(?i)\\s+FROM\\s+|\\s+WHERE\\s+");
        String selectPart = parts[0].replaceFirst("(?i)SELECT\\s+", "").trim();
        List<String> columns = Arrays.asList(selectPart.split("\\s*,\\s*"));

        String tablePart = parts[1].trim();
        String wherePart = parts.length > 2 ? parts[2].trim() : "true";

        // Handle table name (might have trailing content if no WHERE split worked)
        String table = tablePart.split("\\s+")[0];

        BooleanExpr whereExpr = parseWhereClause(wherePart);
        return new SqlQuery(columns, table, whereExpr);
    }

    private static BooleanExpr parseWhereClause(String clause) {
        // Split by AND
        if (clause.contains(" AND ")) {
            String[] andParts = clause.split("\\s+AND\\s+", 2);
            return new AndExpression(parseWhereClause(andParts[0]), parseWhereClause(andParts[1]));
        }
        // Split by OR
        if (clause.contains(" OR ")) {
            String[] orParts = clause.split("\\s+OR\\s+", 2);
            return new OrExpression(parseWhereClause(orParts[0]), parseWhereClause(orParts[1]));
        }
        // Parse comparison: "age > 25" or "active = true"
        clause = clause.trim();
        if (clause.contains(" > ")) {
            String[] p = clause.split("\\s*>\\s*");
            return new GreaterThanExpression(new VariableExpression(p[0].trim()), new NumberExpression(Double.parseDouble(p[1].trim())));
        }
        if (clause.contains(" = ")) {
            String[] p = clause.split("\\s*=\\s*");
            String var = p[0].trim();
            String val = p[1].trim();
            if (val.equals("true") || val.equals("false")) {
                return new EqualExpression(var, Boolean.parseBoolean(val));
            }
            try {
                return new EqualExpression(var, Double.parseDouble(val));
            } catch (NumberFormatException e) {
                return new EqualExpression(var, val);
            }
        }
        return new BooleanExpression(true);
    }
}

// ==================== RULE ENGINE ====================

class Rule {
    private String name;
    private BooleanExpr condition;
    private String action;

    public Rule(String name, BooleanExpr condition, String action) {
        this.name = name;
        this.condition = condition;
        this.action = action;
    }

    public String evaluate(Context context) {
        if (condition.interpret(context)) {
            return "[TRIGGERED] " + name + " -> Action: " + action;
        }
        return "[NOT TRIGGERED] " + name;
    }

    @Override
    public String toString() {
        return "IF " + condition + " THEN " + action;
    }
}

class RuleParser {
    // Parses: "IF temperature > 30 AND humidity > 80 THEN alert"
    public static Rule parse(String ruleStr) {
        String[] parts = ruleStr.split("(?i)\\s+THEN\\s+");
        String conditionStr = parts[0].replaceFirst("(?i)IF\\s+", "").trim();
        String action = parts[1].trim();

        BooleanExpr condition = parseCondition(conditionStr);
        return new Rule(ruleStr, condition, action);
    }

    private static BooleanExpr parseCondition(String cond) {
        if (cond.contains(" AND ")) {
            String[] p = cond.split("\\s+AND\\s+", 2);
            return new AndExpression(parseCondition(p[0]), parseCondition(p[1]));
        }
        if (cond.contains(" OR ")) {
            String[] p = cond.split("\\s+OR\\s+", 2);
            return new OrExpression(parseCondition(p[0]), parseCondition(p[1]));
        }
        cond = cond.trim();
        if (cond.contains(" > ")) {
            String[] p = cond.split("\\s*>\\s*");
            return new GreaterThanExpression(new VariableExpression(p[0].trim()), new NumberExpression(Double.parseDouble(p[1].trim())));
        }
        if (cond.contains(" = ")) {
            String[] p = cond.split("\\s*=\\s*");
            String var = p[0].trim();
            String val = p[1].trim();
            if (val.equals("true") || val.equals("false")) {
                return new EqualExpression(var, Boolean.parseBoolean(val));
            }
            return new EqualExpression(var, val);
        }
        return new BooleanExpression(true);
    }
}

// ==================== MAIN ====================

public class InterpreterPattern {
    public static void main(String[] args) {
        System.out.println("=".repeat(60));
        System.out.println("       INTERPRETER DESIGN PATTERN DEMONSTRATION");
        System.out.println("=".repeat(60));

        // --- Example 1: Mathematical Expressions ---
        System.out.println("\n--- Example 1: Mathematical Expression Interpreter ---\n");

        Context ctx = new Context();
        ctx.setVariable("x", 10.0);
        ctx.setVariable("y", 5.0);
        ctx.setVariable("z", 3.0);

        // Expression: (x + y) * z - 2
        NumericExpr expr = new SubtractExpression(
            new MultiplyExpression(
                new AddExpression(new VariableExpression("x"), new VariableExpression("y")),
                new VariableExpression("z")
            ),
            new NumberExpression(2)
        );

        System.out.println("Context: x=10, y=5, z=3");
        System.out.println("Expression: " + expr);
        System.out.println("Result: " + expr.interpret(ctx));

        // Boolean expression: x > 5 AND y > 2
        BooleanExpr boolExpr = new AndExpression(
            new GreaterThanExpression(new VariableExpression("x"), new NumberExpression(5)),
            new GreaterThanExpression(new VariableExpression("y"), new NumberExpression(2))
        );
        System.out.println("\nBoolean Expression: " + boolExpr);
        System.out.println("Result: " + boolExpr.interpret(ctx));

        // --- Example 2: SQL-like Query Interpreter ---
        System.out.println("\n--- Example 2: SQL-like Query Interpreter ---\n");

        String sql = "SELECT * FROM users WHERE age > 25 AND active = true";
        System.out.println("Query: " + sql);
        SqlQuery query = SqlParser.parse(sql);
        System.out.println("Parsed: " + query);
        System.out.println("Table: " + query.getTable());

        // Simulate rows
        System.out.println("\nEvaluating against rows:");
        List<Map<String, Object>> rows = List.of(
            Map.of("name", "Alice", "age", 30.0, "active", true),
            Map.of("name", "Bob", "age", 22.0, "active", true),
            Map.of("name", "Charlie", "age", 35.0, "active", false),
            Map.of("name", "Diana", "age", 28.0, "active", true)
        );

        for (Map<String, Object> row : rows) {
            Context rowCtx = new Context();
            row.forEach(rowCtx::setVariable);
            boolean matches = query.matches(rowCtx);
            System.out.printf("  %-10s age=%.0f active=%-5s -> %s%n",
                row.get("name"), row.get("age"), row.get("active"),
                matches ? "MATCH" : "no match");
        }

        // --- Example 3: Rule Engine ---
        System.out.println("\n--- Example 3: Rule Engine Interpreter ---\n");

        List<String> ruleStrings = List.of(
            "IF temperature > 30 AND humidity > 80 THEN alert",
            "IF temperature > 40 THEN emergency",
            "IF humidity > 90 OR temperature > 35 THEN warning"
        );

        Context envCtx = new Context();
        envCtx.setVariable("temperature", 38.0);
        envCtx.setVariable("humidity", 85.0);
        System.out.println("Environment: temperature=38, humidity=85\n");

        for (String ruleStr : ruleStrings) {
            Rule rule = RuleParser.parse(ruleStr);
            System.out.println("Rule: " + ruleStr);
            System.out.println("  " + rule.evaluate(envCtx));
            System.out.println();
        }

        System.out.println("=".repeat(60));
        System.out.println("Pattern demonstrates: parsing a language/DSL into an");
        System.out.println("expression tree, then interpreting it against a context.");
        System.out.println("=".repeat(60));
    }
}
