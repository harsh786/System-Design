import java.util.*;

/**
 * Problem: Nested List Weight Sum (LeetCode 339)
 * Approach: DFS with depth parameter, multiply value by depth
 * Time: O(N) total elements, Space: O(D) max depth
 * Production Analogy: Weighted scoring of nested configuration with priority by depth
 */
public class Problem38_NestedListWeightSum {
    interface NestedInteger {
        boolean isInteger();
        Integer getInteger();
        List<NestedInteger> getList();
    }

    static class NI implements NestedInteger {
        Integer val; List<NestedInteger> list;
        NI(int v) { val = v; } NI(List<NestedInteger> l) { list = l; }
        public boolean isInteger() { return val != null; }
        public Integer getInteger() { return val; }
        public List<NestedInteger> getList() { return list; }
    }

    public int depthSum(List<NestedInteger> nestedList) {
        return dfs(nestedList, 1);
    }

    private int dfs(List<NestedInteger> list, int depth) {
        int sum = 0;
        for (NestedInteger ni : list) {
            if (ni.isInteger()) sum += ni.getInteger() * depth;
            else sum += dfs(ni.getList(), depth + 1);
        }
        return sum;
    }

    public static void main(String[] args) {
        // [[1,1],2,[1,1]] => 1*2+1*2+2*1+1*2+1*2 = 10
        List<NestedInteger> inner = Arrays.asList(new NI(1), new NI(1));
        List<NestedInteger> input = Arrays.asList(new NI(inner), new NI(2), new NI(inner));
        System.out.println(new Problem38_NestedListWeightSum().depthSum(input)); // 10
    }
}
