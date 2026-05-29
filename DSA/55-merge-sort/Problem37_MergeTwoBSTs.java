import java.util.*;

public class Problem37_MergeTwoBSTs {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v){val=v;} }
    
    static List<Integer> inorder(TreeNode root) {
        List<Integer> res = new ArrayList<>();
        Deque<TreeNode> stack = new ArrayDeque<>(); TreeNode cur = root;
        while (cur != null || !stack.isEmpty()) {
            while (cur != null) { stack.push(cur); cur = cur.left; }
            cur = stack.pop(); res.add(cur.val); cur = cur.right;
        }
        return res;
    }
    
    static List<Integer> mergeTwoBSTs(TreeNode r1, TreeNode r2) {
        List<Integer> l1 = inorder(r1), l2 = inorder(r2);
        List<Integer> merged = new ArrayList<>();
        int i = 0, j = 0;
        while (i < l1.size() && j < l2.size())
            merged.add(l1.get(i) <= l2.get(j) ? l1.get(i++) : l2.get(j++));
        while (i < l1.size()) merged.add(l1.get(i++));
        while (j < l2.size()) merged.add(l2.get(j++));
        return merged;
    }
    
    public static void main(String[] args) {
        TreeNode r1 = new TreeNode(2); r1.left = new TreeNode(1); r1.right = new TreeNode(4);
        TreeNode r2 = new TreeNode(3); r2.left = new TreeNode(0); r2.right = new TreeNode(5);
        System.out.println(mergeTwoBSTs(r1, r2));
    }
}
