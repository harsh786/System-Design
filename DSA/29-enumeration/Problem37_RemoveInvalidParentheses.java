import java.util.*;

public class Problem37_RemoveInvalidParentheses {
    public List<String> removeInvalidParentheses(String s) {
        List<String> result = new ArrayList<>();
        Queue<String> queue = new LinkedList<>();
        Set<String> visited = new HashSet<>();
        queue.offer(s); visited.add(s);
        boolean found = false;
        while (!queue.isEmpty()) {
            String cur = queue.poll();
            if (isValid(cur)) { result.add(cur); found = true; }
            if (found) continue;
            for (int i = 0; i < cur.length(); i++) {
                if (cur.charAt(i)!='(' && cur.charAt(i)!=')') continue;
                String next = cur.substring(0,i)+cur.substring(i+1);
                if (visited.add(next)) queue.offer(next);
            }
        }
        return result;
    }
    private boolean isValid(String s) { int cnt=0; for (char c:s.toCharArray()) { if (c=='(') cnt++; else if (c==')') { cnt--; if (cnt<0) return false; } } return cnt==0; }
    public static void main(String[] args) { System.out.println(new Problem37_RemoveInvalidParentheses().removeInvalidParentheses("()())()")); }
}
