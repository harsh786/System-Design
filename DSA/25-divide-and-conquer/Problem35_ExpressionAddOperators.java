import java.util.*;

/**
 * Problem 35: Expression Add Operators (LeetCode 282) - Split Approach
 * 
 * D&C Approach:
 * - DIVIDE: At each position, choose to split (insert +, -, *) or extend number
 * - CONQUER: Recursively evaluate remaining string
 * - COMBINE: Check if expression evaluates to target
 * 
 * Time: O(4^n) - at each digit position, 4 choices (join, +, -, *)
 * Space: O(n) recursion depth
 * 
 * Production Analogy:
 * - Expression parsing in calculators/compilers
 * - Code generation for arithmetic expressions
 * - Search query expansion with operators
 */
public class Problem35_ExpressionAddOperators {

    public static List<String> addOperators(String num, int target) {
        List<String> result = new ArrayList<>();
        if (num == null || num.isEmpty()) return result;
        dfs(num, target, 0, 0, 0, "", result);
        return result;
    }

    private static void dfs(String num, int target, int idx, long eval, long multed, String path, List<String> result) {
        if (idx == num.length()) {
            if (eval == target) result.add(path);
            return;
        }
        
        for (int i = idx; i < num.length(); i++) {
            if (i != idx && num.charAt(idx) == '0') break; // No leading zeros
            long cur = Long.parseLong(num.substring(idx, i + 1));
            
            if (idx == 0) {
                dfs(num, target, i + 1, cur, cur, "" + cur, result);
            } else {
                dfs(num, target, i + 1, eval + cur, cur, path + "+" + cur, result);
                dfs(num, target, i + 1, eval - cur, -cur, path + "-" + cur, result);
                // For multiplication: undo last addition, apply multiplication
                dfs(num, target, i + 1, eval - multed + multed * cur, multed * cur, path + "*" + cur, result);
            }
        }
    }

    public static void main(String[] args) {
        System.out.println(addOperators("123", 6));      // ["1+2+3","1*2*3"]
        System.out.println(addOperators("232", 8));      // ["2*3+2","2+3*2"]
        System.out.println(addOperators("105", 5));      // ["1*0+5","10-5"]
        System.out.println(addOperators("00", 0));       // ["0+0","0-0","0*0"]
        System.out.println(addOperators("3456237490", 9191)); // []
    }
}
