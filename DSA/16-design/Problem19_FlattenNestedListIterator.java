import java.util.*;

/**
 * Problem 19: Flatten Nested List Iterator
 * 
 * API Contract:
 * - next(): Return next integer
 * - hasNext(): Check if integers remain
 * 
 * Complexity: O(1) amortized for next/hasNext
 * Data Structure: Stack of iterators (lazy flattening)
 * 
 * Production Analogy: JSON/XML deep traversal, file system recursive listing,
 * nested comment thread flattening, recursive data structure serialization
 */
public class Problem19_FlattenNestedListIterator {

    // Simplified NestedInteger interface
    static class NestedInteger {
        private Integer val;
        private List<NestedInteger> list;

        NestedInteger(int v) { val = v; }
        NestedInteger(List<NestedInteger> l) { list = l; }

        boolean isInteger() { return val != null; }
        Integer getInteger() { return val; }
        List<NestedInteger> getList() { return list; }
    }

    static class NestedIterator implements Iterator<Integer> {
        private Deque<Iterator<NestedInteger>> stack;
        private Integer nextVal;

        public NestedIterator(List<NestedInteger> nestedList) {
            stack = new ArrayDeque<>();
            stack.push(nestedList.iterator());
        }

        @Override
        public Integer next() {
            if (!hasNext()) throw new NoSuchElementException();
            Integer result = nextVal;
            nextVal = null;
            return result;
        }

        @Override
        public boolean hasNext() {
            if (nextVal != null) return true;
            while (!stack.isEmpty()) {
                Iterator<NestedInteger> it = stack.peek();
                if (!it.hasNext()) { stack.pop(); continue; }
                NestedInteger ni = it.next();
                if (ni.isInteger()) { nextVal = ni.getInteger(); return true; }
                stack.push(ni.getList().iterator());
            }
            return false;
        }
    }

    public static void main(String[] args) {
        // [[1,1],2,[1,1]]
        List<NestedInteger> input = Arrays.asList(
            new NestedInteger(Arrays.asList(new NestedInteger(1), new NestedInteger(1))),
            new NestedInteger(2),
            new NestedInteger(Arrays.asList(new NestedInteger(1), new NestedInteger(1)))
        );
        NestedIterator it = new NestedIterator(input);
        List<Integer> result = new ArrayList<>();
        while (it.hasNext()) result.add(it.next());
        assert result.equals(Arrays.asList(1, 1, 2, 1, 1));

        // Edge: empty nested list [[]]
        List<NestedInteger> empty = Arrays.asList(new NestedInteger(new ArrayList<>()));
        NestedIterator it2 = new NestedIterator(empty);
        assert !it2.hasNext();

        System.out.println("All tests passed!");
    }
}
