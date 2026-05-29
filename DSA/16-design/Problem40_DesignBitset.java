import java.util.*;

/**
 * Problem 40: Design Bitset
 * 
 * API Contract:
 * - fix(idx): Set bit at idx to 1
 * - unfix(idx): Set bit at idx to 0
 * - flip(): Flip all bits
 * - all(): Return true if all bits are 1
 * - one(): Return true if at least one bit is 1
 * - count(): Return number of 1-bits
 * - toString(): Return string representation
 * 
 * Complexity: O(1) for all except toString O(n)
 * Data Structure: Array + flip flag + ones counter (lazy flip approach)
 * 
 * Production Analogy: Bitmap indexes in databases, feature flags,
 * permission bit masks, bloom filter backing
 */
public class Problem40_DesignBitset {

    static class Bitset {
        private int[] bits;
        private int size, ones;
        private boolean flipped;

        public Bitset(int size) {
            this.size = size;
            bits = new int[size];
            ones = 0;
            flipped = false;
        }

        public void fix(int idx) {
            if (!flipped && bits[idx] == 0) { bits[idx] = 1; ones++; }
            else if (flipped && bits[idx] == 1) { bits[idx] = 0; ones++; }
        }

        public void unfix(int idx) {
            if (!flipped && bits[idx] == 1) { bits[idx] = 0; ones--; }
            else if (flipped && bits[idx] == 0) { bits[idx] = 1; ones--; }
        }

        public void flip() { flipped = !flipped; ones = size - ones; }
        public boolean all() { return ones == size; }
        public boolean one() { return ones > 0; }
        public int count() { return ones; }

        public String toString() {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < size; i++) {
                int val = flipped ? 1 - bits[i] : bits[i];
                sb.append(val);
            }
            return sb.toString();
        }
    }

    public static void main(String[] args) {
        Bitset bs = new Bitset(5);
        bs.fix(3);
        bs.fix(1);
        bs.flip();
        assert bs.all() == false;
        bs.unfix(0);
        bs.flip();
        assert bs.one() == true;
        bs.unfix(0);
        assert bs.count() == 2;
        assert bs.toString().equals("01010");

        // Edge: all set
        Bitset bs2 = new Bitset(3);
        bs2.fix(0); bs2.fix(1); bs2.fix(2);
        assert bs2.all();
        bs2.flip();
        assert !bs2.one();

        System.out.println("All tests passed!");
    }
}
