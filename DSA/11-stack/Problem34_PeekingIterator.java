import java.util.*;

/**
 * Problem 34: Peeking Iterator (LeetCode 284)
 * 
 * Design iterator that supports peek() in addition to next() and hasNext().
 * 
 * Approach: Cache the next element. On peek, return cached without advancing.
 * On next, return cached and advance.
 * 
 * Time Complexity: O(1) for all operations
 * Space Complexity: O(1) extra
 * 
 * Production Analogy: Like buffered readers in I/O systems that allow lookahead
 * without consuming the stream - essential for parsers and protocol handlers.
 */
public class Problem34_PeekingIterator {

    static class PeekingIteratorImpl implements Iterator<Integer> {
        Iterator<Integer> iter;
        Integer peeked = null;

        public PeekingIteratorImpl(Iterator<Integer> iterator) { iter = iterator; }

        public Integer peek() {
            if (peeked == null) peeked = iter.next();
            return peeked;
        }

        public Integer next() {
            if (peeked != null) { Integer val = peeked; peeked = null; return val; }
            return iter.next();
        }

        public boolean hasNext() { return peeked != null || iter.hasNext(); }
    }

    public static void main(String[] args) {
        PeekingIteratorImpl it = new PeekingIteratorImpl(Arrays.asList(1, 2, 3).iterator());
        System.out.println(it.next());    // 1
        System.out.println(it.peek());    // 2
        System.out.println(it.next());    // 2
        System.out.println(it.next());    // 3
        System.out.println(it.hasNext()); // false
    }
}
