import java.util.*;

/**
 * Problem 18: Peeking Iterator
 * 
 * API Contract:
 * - peek(): Return next element without advancing
 * - next(): Return next element and advance
 * - hasNext(): Check if elements remain
 * 
 * Complexity: O(1) for all operations
 * Data Structure: Wrapper around iterator with cached next value
 * 
 * Production Analogy: Lookahead in parsers/lexers, stream processing with peek,
 * buffered readers, compiler tokenizers
 */
public class Problem18_PeekingIterator {

    static class PeekingIter implements Iterator<Integer> {
        private Iterator<Integer> iter;
        private Integer peeked;
        private boolean hasPeeked;

        public PeekingIter(Iterator<Integer> iterator) {
            this.iter = iterator;
        }

        public Integer peek() {
            if (!hasPeeked) {
                peeked = iter.next();
                hasPeeked = true;
            }
            return peeked;
        }

        @Override
        public Integer next() {
            if (hasPeeked) {
                hasPeeked = false;
                return peeked;
            }
            return iter.next();
        }

        @Override
        public boolean hasNext() {
            return hasPeeked || iter.hasNext();
        }
    }

    public static void main(String[] args) {
        List<Integer> list = Arrays.asList(1, 2, 3);
        PeekingIter pi = new PeekingIter(list.iterator());
        assert pi.peek() == 1;
        assert pi.peek() == 1; // peek doesn't advance
        assert pi.next() == 1;
        assert pi.next() == 2;
        assert pi.peek() == 3;
        assert pi.hasNext();
        assert pi.next() == 3;
        assert !pi.hasNext();

        System.out.println("All tests passed!");
    }
}
