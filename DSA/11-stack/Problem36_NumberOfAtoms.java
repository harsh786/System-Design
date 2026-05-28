import java.util.*;

/**
 * Problem 36: Number of Atoms (LeetCode 726)
 * 
 * Parse chemical formula and return count of each atom sorted by name.
 * 
 * Approach: Stack of maps. On '(' push new map. On ')' pop and multiply by count,
 * merge into previous map. Build atom names and counts character by character.
 * 
 * Time Complexity: O(n^2) worst case due to string building
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like parsing nested resource definitions in IaC templates
 * where multipliers (count/for_each) affect all nested resources.
 */
public class Problem36_NumberOfAtoms {

    public static String countOfAtoms(String formula) {
        Deque<Map<String, Integer>> stack = new ArrayDeque<>();
        stack.push(new TreeMap<>());
        int i = 0, n = formula.length();
        while (i < n) {
            if (formula.charAt(i) == '(') {
                stack.push(new TreeMap<>());
                i++;
            } else if (formula.charAt(i) == ')') {
                i++;
                int count = 0;
                while (i < n && Character.isDigit(formula.charAt(i))) {
                    count = count * 10 + (formula.charAt(i++) - '0');
                }
                if (count == 0) count = 1;
                Map<String, Integer> top = stack.pop();
                Map<String, Integer> curr = stack.peek();
                for (var e : top.entrySet()) {
                    curr.merge(e.getKey(), e.getValue() * count, Integer::sum);
                }
            } else {
                StringBuilder atom = new StringBuilder();
                atom.append(formula.charAt(i++));
                while (i < n && Character.isLowerCase(formula.charAt(i))) {
                    atom.append(formula.charAt(i++));
                }
                int count = 0;
                while (i < n && Character.isDigit(formula.charAt(i))) {
                    count = count * 10 + (formula.charAt(i++) - '0');
                }
                if (count == 0) count = 1;
                stack.peek().merge(atom.toString(), count, Integer::sum);
            }
        }
        StringBuilder sb = new StringBuilder();
        for (var e : stack.peek().entrySet()) {
            sb.append(e.getKey());
            if (e.getValue() > 1) sb.append(e.getValue());
        }
        return sb.toString();
    }

    public static void main(String[] args) {
        System.out.println(countOfAtoms("H2O"));          // H2O
        System.out.println(countOfAtoms("Mg(OH)2"));      // H2MgO2
        System.out.println(countOfAtoms("K4(ON(SO3)2)2")); // K4N2O14S4
    }
}
