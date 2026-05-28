import java.util.*;

/**
 * Problem 32: Flatten Nested List Iterator (LeetCode 341)
 * 
 * Implement an iterator to flatten a nested list of integers.
 * 
 * Approach: Use stack of iterators. When current element is a list, push its
 * iterator onto stack. Always ensure top of stack points to next integer.
 * 
 * Time Complexity: O(1) amortized for next/hasNext
 * Space Complexity: O(d) where d = max nesting depth
 * 
 * Production Analogy: Like flattening nested JSON responses from paginated APIs
 * into a single stream for downstream consumers.
 */
public class Problem32_FlattenNestedListIterator {

    // Simplified NestedInteger interface
    interface NestedInteger {
        boolean isInteger();
        Integer getInteger();
        List<NestedInteger> getList();
    }

    static class NestedIntegerImpl implements NestedInteger {
        Integer val;
        List<NestedInteger> list;
        NestedIntegerImpl(int v) { val = v; }
        NestedIntegerImpl(List<NestedInteger> l) { list = l; }
        public boolean isInteger() { return val != null; }
        public Integer getInteger() { return val; }
        public List<NestedInteger> getList() { return list; }
    }

    static class NestedIterator implements Iterator<Integer> {
        Deque<Iterator<NestedInteger>> stack = new ArrayDeque<>();
        Integer next = null;

        public NestedIterator(List<NestedInteger> nestedList) {
            stack.push(nestedList.iterator());
        }

        public Integer next() { Integer n = next; next = null; return n; }

        public boolean hasNext() {
            if (next != null) return true;
            while (!stack.isEmpty()) {
                Iterator<NestedInteger> it = stack.peek();
                if (!it.hasNext()) { stack.pop(); continue; }
                NestedInteger ni = it.next();
                if (ni.isInteger()) { next = ni.getInteger(); return true; }
                stack.push(ni.getList().iterator());
            }
            return false;
        }
    }

    public static void main(String[] args) {
        // [[1,1],2,[1,1]]
        List<NestedInteger> list = Arrays.asList(
            new NestedIntegerImpl(Arrays.asList(new NestedIntegerImpl(1), new NestedIntegerImpl(1))),
            new NestedIntegerImpl(2),
            new NestedIntegerImpl(Arrays.asList(new NestedIntegerImpl(1), new NestedIntegerImpl(1)))
        );
        NestedIterator it = new NestedIterator(list);
        while (it.hasNext()) System.out.print(it.next() + " "); // 1 1 2 1 1
        System.out.println();

        // [1,[4,[6]]]
        List<NestedInteger> list2 = Arrays.asList(
            new NestedIntegerImpl(1),
            new NestedIntegerImpl(Arrays.asList(
                new NestedIntegerImpl(4),
                new NestedIntegerImpl(Arrays.asList(new NestedIntegerImpl(6)))
            ))
        );
        NestedIterator it2 = new NestedIterator(list2);
        while (it2.hasNext()) System.out.print(it2.next() + " "); // 1 4 6
        System.out.println();
    }
}
