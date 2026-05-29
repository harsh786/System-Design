import java.util.*;

public class Problem50_RecursiveToIterativeConversionExamples {
    // Example 1: Factorial - recursive vs iterative
    static long factorialRecursive(int n) { return n <= 1 ? 1 : n * factorialRecursive(n - 1); }
    static long factorialIterative(int n) { long res = 1; for (int i = 2; i <= n; i++) res *= i; return res; }

    // Example 2: Tree inorder - recursive vs iterative
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }
    static List<Integer> inorderRecursive(TreeNode root) {
        List<Integer> res = new ArrayList<>();
        inorderHelper(root, res); return res;
    }
    static void inorderHelper(TreeNode node, List<Integer> res) {
        if (node == null) return;
        inorderHelper(node.left, res); res.add(node.val); inorderHelper(node.right, res);
    }
    static List<Integer> inorderIterative(TreeNode root) {
        List<Integer> res = new ArrayList<>(); Stack<TreeNode> stack = new Stack<>();
        TreeNode cur = root;
        while (cur != null || !stack.isEmpty()) {
            while (cur != null) { stack.push(cur); cur = cur.left; }
            cur = stack.pop(); res.add(cur.val); cur = cur.right;
        }
        return res;
    }

    // Example 3: DFS on graph - recursive vs iterative
    static void dfsRecursive(Map<Integer, List<Integer>> graph, int node, Set<Integer> visited) {
        visited.add(node); System.out.print(node + " ");
        for (int next : graph.getOrDefault(node, Collections.emptyList()))
            if (!visited.contains(next)) dfsRecursive(graph, next, visited);
    }
    static void dfsIterative(Map<Integer, List<Integer>> graph, int start) {
        Stack<Integer> stack = new Stack<>(); Set<Integer> visited = new HashSet<>();
        stack.push(start);
        while (!stack.isEmpty()) {
            int node = stack.pop();
            if (visited.contains(node)) continue;
            visited.add(node); System.out.print(node + " ");
            for (int next : graph.getOrDefault(node, Collections.emptyList()))
                if (!visited.contains(next)) stack.push(next);
        }
    }

    public static void main(String[] args) {
        System.out.println("Factorial recursive: " + factorialRecursive(10));
        System.out.println("Factorial iterative: " + factorialIterative(10));

        TreeNode root = new TreeNode(4); root.left = new TreeNode(2); root.right = new TreeNode(6);
        root.left.left = new TreeNode(1); root.left.right = new TreeNode(3);
        System.out.println("Inorder recursive: " + inorderRecursive(root));
        System.out.println("Inorder iterative: " + inorderIterative(root));

        Map<Integer, List<Integer>> graph = new HashMap<>();
        graph.put(0, Arrays.asList(1, 2)); graph.put(1, Arrays.asList(3)); graph.put(2, Arrays.asList(3)); graph.put(3, Arrays.asList());
        System.out.print("DFS recursive: "); dfsRecursive(graph, 0, new HashSet<>()); System.out.println();
        System.out.print("DFS iterative: "); dfsIterative(graph, 0); System.out.println();
    }
}
