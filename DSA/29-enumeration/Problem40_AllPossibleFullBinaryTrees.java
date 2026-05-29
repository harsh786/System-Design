import java.util.*;

public class Problem40_AllPossibleFullBinaryTrees {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v){val=v;} }
    Map<Integer, List<TreeNode>> memo = new HashMap<>();
    public List<TreeNode> allPossibleFBT(int n) {
        if (memo.containsKey(n)) return memo.get(n);
        List<TreeNode> result = new ArrayList<>();
        if (n == 1) { result.add(new TreeNode(0)); }
        else if (n % 2 == 1) {
            for (int i = 1; i < n; i += 2)
                for (TreeNode l : allPossibleFBT(i))
                    for (TreeNode r : allPossibleFBT(n-1-i)) { TreeNode root = new TreeNode(0); root.left=l; root.right=r; result.add(root); }
        }
        memo.put(n, result); return result;
    }
    public static void main(String[] args) { System.out.println("Full binary trees with 7 nodes: " + new Problem40_AllPossibleFullBinaryTrees().allPossibleFBT(7).size()); }
}
