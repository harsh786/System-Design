import java.util.*;

/**
 * Problem 17: Expression Add Operators (LeetCode 282)
 * 
 * Given a string of digits and a target, add +, -, * between digits to reach target.
 * 
 * Search Tree:
 * - At each position, decide how many digits form the next number (1 to remaining)
 * - Then decide operator: +, -, * (no operator for first number)
 * 
 * Pruning Strategy:
 * - Skip numbers with leading zeros (except "0" itself)
 * - Track 'prev' operand for multiplication precedence handling
 * 
 * Time Complexity: O(4^n * n) - at each gap, 4 choices (no op, +, -, *)
 * Space Complexity: O(n)
 * 
 * Production Analogy:
 * - Expression evaluation engines: parsing and evaluating user-defined formulas dynamically.
 */
public class Problem17_ExpressionAddOperators {

    public List<String> addOperators(String num, int target) {
        List<String> result = new ArrayList<>();
        backtrack(num, target, 0, 0, 0, new StringBuilder(), result);
        return result;
    }

    private void backtrack(String num, int target, int index, long eval, long prev, StringBuilder expr, List<String> result) {
        if (index == num.length()) {
            if (eval == target) result.add(expr.toString());
            return;
        }
        int len = expr.length();
        for (int i = index; i < num.length(); i++) {
            if (i > index && num.charAt(index) == '0') break; // no leading zeros
            long curr = Long.parseLong(num.substring(index, i + 1));
            if (index == 0) {
                expr.append(curr);
                backtrack(num, target, i + 1, curr, curr, expr, result);
                expr.setLength(len);
            } else {
                // Try +
                expr.append('+').append(curr);
                backtrack(num, target, i + 1, eval + curr, curr, expr, result);
                expr.setLength(len);
                // Try -
                expr.append('-').append(curr);
                backtrack(num, target, i + 1, eval - curr, -curr, expr, result);
                expr.setLength(len);
                // Try *
                expr.append('*').append(curr);
                backtrack(num, target, i + 1, eval - prev + prev * curr, prev * curr, expr, result);
                expr.setLength(len);
            }
        }
    }

    public static void main(String[] args) {
        Problem17_ExpressionAddOperators sol = new Problem17_ExpressionAddOperators();

        System.out.println(sol.addOperators("123", 6));   // [1+2+3, 1*2*3]
        System.out.println(sol.addOperators("232", 8));   // [2+3*2, 2*3+2]
        System.out.println(sol.addOperators("105", 5));   // [1*0+5, 10-5]
        System.out.println(sol.addOperators("00", 0));    // [0+0, 0-0, 0*0]
        System.out.println(sol.addOperators("3456237490", 9191));
    }
}
