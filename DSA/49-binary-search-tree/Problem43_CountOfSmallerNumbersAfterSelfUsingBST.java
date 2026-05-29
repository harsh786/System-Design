import java.util.*;

public class Problem43_CountOfSmallerNumbersAfterSelfUsingBST {
    static class BSTNode { int val, count, leftSize; BSTNode left, right; BSTNode(int v) { val = v; count = 1; } }

    public static List<Integer> countSmaller(int[] nums) {
        Integer[] result = new Integer[nums.length];
        BSTNode root = null;
        for (int i = nums.length - 1; i >= 0; i--) {
            root = insert(root, nums[i], result, i, 0);
        }
        return Arrays.asList(result);
    }

    private static BSTNode insert(BSTNode node, int val, Integer[] result, int idx, int smaller) {
        if (node == null) { node = new BSTNode(val); result[idx] = smaller; return node; }
        if (val < node.val) { node.leftSize++; node.left = insert(node.left, val, result, idx, smaller); }
        else if (val > node.val) { node.right = insert(node.right, val, result, idx, smaller + node.leftSize + node.count); }
        else { node.count++; result[idx] = smaller + node.leftSize; }
        return node;
    }

    public static void main(String[] args) {
        System.out.println(countSmaller(new int[]{5, 2, 6, 1})); // [2,1,1,0]
    }
}
