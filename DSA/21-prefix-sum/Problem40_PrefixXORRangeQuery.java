/**
 * Problem 40: Prefix XOR Range Query
 * 
 * Pattern: prefix[i] = XOR of nums[0..i-1]. XOR(l..r) = prefix[r+1] ^ prefix[l]
 * (XOR is its own inverse, so same prefix-sum trick works)
 * 
 * Time: O(n) build, O(1) query
 * Space: O(n)
 * 
 * Production Analogy: Computing parity checks over data segments for error
 * detection in distributed storage (RAID-like XOR parity).
 */
public class Problem40_PrefixXORRangeQuery {

    static class XORArray {
        private int[] prefix;

        public XORArray(int[] nums) {
            prefix = new int[nums.length + 1];
            for (int i = 0; i < nums.length; i++)
                prefix[i + 1] = prefix[i] ^ nums[i];
        }

        public int xorRange(int left, int right) {
            return prefix[right + 1] ^ prefix[left];
        }
    }

    public static void main(String[] args) {
        XORArray xa = new XORArray(new int[]{1, 3, 4, 8});
        assert xa.xorRange(0, 1) == 2;  // 1^3 = 2
        assert xa.xorRange(1, 2) == 7;  // 3^4 = 7
        assert xa.xorRange(0, 3) == 14; // 1^3^4^8 = 14
        assert xa.xorRange(2, 2) == 4;  // just 4

        XORArray xa2 = new XORArray(new int[]{5, 5, 5, 5});
        assert xa2.xorRange(0, 1) == 0;
        assert xa2.xorRange(0, 3) == 0;
        System.out.println("All tests passed!");
    }
}
