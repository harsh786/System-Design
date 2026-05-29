import java.util.*;

public class Problem38_DifferentWaysToAddParentheses {
    public List<Integer> diffWaysToCompute(String expression) {
        List<Integer> result = new ArrayList<>();
        for (int i = 0; i < expression.length(); i++) {
            char c = expression.charAt(i);
            if (c=='+' || c=='-' || c=='*') {
                List<Integer> left = diffWaysToCompute(expression.substring(0,i));
                List<Integer> right = diffWaysToCompute(expression.substring(i+1));
                for (int l : left) for (int r : right) {
                    if (c=='+') result.add(l+r); else if (c=='-') result.add(l-r); else result.add(l*r);
                }
            }
        }
        if (result.isEmpty()) result.add(Integer.parseInt(expression));
        return result;
    }
    public static void main(String[] args) { System.out.println(new Problem38_DifferentWaysToAddParentheses().diffWaysToCompute("2*3-4*5")); }
}
