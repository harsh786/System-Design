import java.util.*;

public class Problem17_BSTIteratorII {
    // BST Iterator with prev() support
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v){val=v;} }
    List<Integer> sorted = new ArrayList<>();
    int idx = -1;

    public Problem17_BSTIteratorII(TreeNode root) { inorder(root); }
    void inorder(TreeNode n) { if(n!=null){inorder(n.left);sorted.add(n.val);inorder(n.right);} }

    public boolean hasNext() { return idx < sorted.size() - 1; }
    public boolean hasPrev() { return idx > 0; }
    public int next() { return sorted.get(++idx); }
    public int prev() { return sorted.get(--idx); }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(5);
        root.left = new TreeNode(3); root.right = new TreeNode(7);
        Problem17_BSTIteratorII it = new Problem17_BSTIteratorII(root);
        System.out.println(it.next()); // 3
        System.out.println(it.next()); // 5
        System.out.println(it.prev()); // 3
        System.out.println(it.next()); // 5
        System.out.println(it.next()); // 7
    }
}
