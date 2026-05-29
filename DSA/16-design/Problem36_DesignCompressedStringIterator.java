import java.util.*;

/**
 * Problem 36: Design Compressed String Iterator
 * 
 * API Contract:
 * - next(): Return next character or ' ' if exhausted
 * - hasNext(): Return true if characters remain
 * 
 * Complexity: O(1) per call
 * Data Structure: Parse compressed string, track current char and remaining count
 * 
 * Production Analogy: Run-length encoding decompression, streaming decoders,
 * data compression libraries, image format decoders (BMP RLE)
 */
public class Problem36_DesignCompressedStringIterator {

    static class StringIterator {
        private String s;
        private int idx;
        private char currentChar;
        private int count;

        public StringIterator(String compressedString) {
            s = compressedString;
            idx = 0;
            advance();
        }

        private void advance() {
            if (idx >= s.length()) return;
            currentChar = s.charAt(idx++);
            count = 0;
            while (idx < s.length() && Character.isDigit(s.charAt(idx))) {
                count = count * 10 + (s.charAt(idx++) - '0');
            }
        }

        public char next() {
            if (!hasNext()) return ' ';
            char result = currentChar;
            count--;
            if (count == 0) advance();
            return result;
        }

        public boolean hasNext() {
            return count > 0;
        }
    }

    public static void main(String[] args) {
        StringIterator it = new StringIterator("L1e2t1C1o1d1e1");
        assert it.next() == 'L';
        assert it.next() == 'e';
        assert it.next() == 'e';
        assert it.next() == 't';
        assert it.hasNext();
        assert it.next() == 'C';
        assert it.next() == 'o';
        assert it.next() == 'd';
        assert it.next() == 'e';
        assert !it.hasNext();
        assert it.next() == ' ';

        // Large count
        StringIterator it2 = new StringIterator("a100");
        for (int i = 0; i < 100; i++) assert it2.next() == 'a';
        assert !it2.hasNext();

        System.out.println("All tests passed!");
    }
}
