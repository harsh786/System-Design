import java.util.*;

/**
 * Problem: Flatten Nested List Iterator (LeetCode 341)
 * Approach: Use stack to lazily flatten nested structure via DFS
 * Time: O(1) amortized per next(), Space: O(D) depth
 * Production Analogy: Lazy evaluation of deeply nested API responses for streaming
 */
public class Problem39_FlattenNestedListIterator {
    interface NestedInteger {
        boolean isInteger(); Integer getInteger(); List<NestedInteger> getList();
    }
    static class NI implements NestedInteger {
        Integer val; List<NestedInteger> list;
        NI(int v) { val = v; } NI(List<NestedInteger> l) { list = l; }
        public boolean isInteger() { return val != null; }
        public Integer getInteger() { return val; }
        public List<NestedInteger> getList() { return list; }
    }

    static class NestedIterator implements Iterator<Integer> {
        Deque<Iterator<NestedInteger>> stack = new ArrayDeque<>();
        Integer next;

        public NestedIterator(List<NestedInteger> nestedList) {
            stack.push(nestedList.iterator());
        }

        public boolean hasNext() {
            while (next == null && !stack.isEmpty()) {
                if (!stack.peek().hasNext()) { stack.pop(); continue; }
                NestedInteger ni = stack.peek().next();
                if (ni.isInteger()) next = ni.getInteger();
                else stack.push(ni.getList().iterator());
            }
            return next != null;
        }

        public Integer next() { Integer val = next; next = null; return val; }
    }

    public static void main(String[] args) {
        List<NestedInteger> inner = Arrays.asList(new NI(1), new NI(1));
        List<NestedInteger> input = Arrays.asList(new NI(inner), new NI(2), new NI(inner));
        NestedIterator it = new NestedIterator(input);
        while (it.hasNext()) System.out.print(it.next() + " "); // 1 1 2 1 1
    }
}
