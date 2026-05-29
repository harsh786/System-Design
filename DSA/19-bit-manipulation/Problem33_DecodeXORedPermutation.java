/**
 * Problem 33: Decode XORed Permutation
 * encoded[i] = perm[i] ^ perm[i+1]. perm is permutation of [1..n] (n is odd).
 * 
 * Approach: XOR of all [1..n] is known. XOR of odd-indexed encoded gives XOR of perm[1..n-1].
 * So perm[0] = totalXOR ^ xor(encoded[1],encoded[3],...).
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Recovering original routing table from XOR-compressed diffs.
 */
public class Problem33_DecodeXORedPermutation {
    public static int[] decode(int[] encoded) {
        int n = encoded.length + 1;
        int totalXor = 0;
        for (int i = 1; i <= n; i++) totalXor ^= i;
        // XOR of encoded[1], encoded[3], ... = perm[1]^perm[2]^...^perm[n-1]
        int oddXor = 0;
        for (int i = 1; i < encoded.length; i += 2) oddXor ^= encoded[i];
        int[] perm = new int[n];
        perm[0] = totalXor ^ oddXor;
        for (int i = 0; i < encoded.length; i++) {
            perm[i + 1] = perm[i] ^ encoded[i];
        }
        return perm;
    }

    public static void main(String[] args) {
        int[] r = decode(new int[]{3, 1});
        for (int v : r) System.out.print(v + " "); // 1 2 3
        System.out.println();
        r = decode(new int[]{6, 5, 4, 6});
        for (int v : r) System.out.print(v + " "); // 2 4 1 5 3
        System.out.println();
    }
}
