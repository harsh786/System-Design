import java.util.*;

/**
 * Problem 7: Different Ways to Add Parentheses (LeetCode 241)
 * 
 * D&C Approach:
 * - DIVIDE: Split expression at each operator
 * - CONQUER: Recursively compute all results for left and right sub-expressions
 * - COMBINE: Apply the operator to every combination of left/right results
 * 
 * Time: O(Catalan(n)) where n = number of operators (exponential)
 * Space: O(Catalan(n)) for storing all possible results
 * 
 * Production Analogy:
 * - Query plan enumeration in SQL optimizers (all possible join orders)
 * - Expression evaluation in compilers with different associativity rules
 */
public class Problem07_DifferentWaysToAddParentheses {

    public static List<Integer> diffWaysToCompute(String expression) {
        List<Integer> result = new ArrayList<>();
        
        for (int i = 0; i < expression.length(); i++) {
            char c = expression.charAt(i);
            if (c == '+' || c == '-' || c == '*') {
                List<Integer> left = diffWaysToCompute(expression.substring(0, i));
                List<Integer> right = diffWaysToCompute(expression.substring(i + 1));
                
                for (int l : left) {
                    for (int r : right) {
                        if (c == '+') result.add(l + r);
                        else if (c == '-') result.add(l - r);
                        else result.add(l * r);
                    }
                }
            }
        }
        
        // Base case: pure number
        if (result.isEmpty()) result.add(Integer.parseInt(expression));
        return result;
    }

    public static void main(String[] args) {
        System.out.println(diffWaysToCompute("2-1-1"));     // [0, 2]
        System.out.println(diffWaysToCompute("2*3-4*5"));   // [-34,-14,-10,-10,10]
        System.out.println(diffWaysToCompute("1"));         // [1]
        System.out.println(diffWaysToCompute("1+1"));       // [2]
        System.out.println(diffWaysToCompute("2*2*2"));     // [8, 8]
    }
}
