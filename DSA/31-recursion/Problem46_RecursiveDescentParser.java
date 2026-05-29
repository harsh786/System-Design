public class Problem46_RecursiveDescentParser {
    // Parses and evaluates: expr = term (('+' | '-') term)*; term = factor (('*' | '/') factor)*; factor = number | '(' expr ')'
    static String input; static int pos;
    public static double evaluate(String expression) {
        input = expression.replaceAll("\\s+", ""); pos = 0;
        return expr();
    }
    static double expr() {
        double result = term();
        while (pos < input.length() && (input.charAt(pos) == '+' || input.charAt(pos) == '-')) {
            char op = input.charAt(pos++);
            double right = term();
            result = op == '+' ? result + right : result - right;
        }
        return result;
    }
    static double term() {
        double result = factor();
        while (pos < input.length() && (input.charAt(pos) == '*' || input.charAt(pos) == '/')) {
            char op = input.charAt(pos++);
            double right = factor();
            result = op == '*' ? result * right : result / right;
        }
        return result;
    }
    static double factor() {
        if (input.charAt(pos) == '(') { pos++; double r = expr(); pos++; return r; }
        int start = pos;
        while (pos < input.length() && (Character.isDigit(input.charAt(pos)) || input.charAt(pos) == '.')) pos++;
        return Double.parseDouble(input.substring(start, pos));
    }
    public static void main(String[] args) {
        System.out.println(evaluate("3 + 5 * 2")); // 13.0
        System.out.println(evaluate("(3 + 5) * 2")); // 16.0
        System.out.println(evaluate("10 / 2 + 3")); // 8.0
    }
}
