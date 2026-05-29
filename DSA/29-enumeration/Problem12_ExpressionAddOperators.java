import java.util.*;

public class Problem12_ExpressionAddOperators {
    public List<String> addOperators(String num, int target) {
        List<String> result = new ArrayList<>();
        dfs(result, num, target, 0, 0, 0, new StringBuilder());
        return result;
    }

    private void dfs(List<String> result, String num, int target, int idx, long eval, long multed, StringBuilder path) {
        if (idx == num.length()) { if (eval == target) result.add(path.toString()); return; }
        for (int i = idx; i < num.length(); i++) {
            if (i > idx && num.charAt(idx) == '0') break;
            long cur = Long.parseLong(num.substring(idx, i+1));
            int len = path.length();
            if (idx == 0) { path.append(cur); dfs(result,num,target,i+1,cur,cur,path); path.setLength(len); }
            else {
                path.append('+').append(cur); dfs(result,num,target,i+1,eval+cur,cur,path); path.setLength(len);
                path.append('-').append(cur); dfs(result,num,target,i+1,eval-cur,-cur,path); path.setLength(len);
                path.append('*').append(cur); dfs(result,num,target,i+1,eval-multed+multed*cur,multed*cur,path); path.setLength(len);
            }
        }
    }

    public static void main(String[] args) { System.out.println(new Problem12_ExpressionAddOperators().addOperators("123",6)); }
}
