/**
 * Problem 34: Count Triplets That Can Form Two Arrays of Equal XOR
 * Find (i,j,k) where XOR(arr[i..j-1]) == XOR(arr[j..k]).
 * 
 * Approach: If XOR(i..k) == 0, then any j in (i,k] works -> contributes (k-i) triplets.
 * Use prefix XOR.
 * Time: O(n^2), Space: O(n)
 * 
 * Production Analogy: Finding balanced partitions in distributed XOR-based checksums.
 */
public class Problem34_CountTripletsEqualXOR {
    public static int countTriplets(int[] arr) {
        int n = arr.length, count = 0;
        int[] prefix = new int[n + 1];
        for (int i = 0; i < n; i++) prefix[i + 1] = prefix[i] ^ arr[i];
        for (int i = 0; i < n; i++)
            for (int k = i + 1; k < n; k++)
                if (prefix[i] == prefix[k + 1])
                    count += (k - i);
        return count;
    }

    public static void main(String[] args) {
        System.out.println(countTriplets(new int[]{2,3,1,6,7})); // 4
        System.out.println(countTriplets(new int[]{1,1,1,1,1})); // 10
    }
}
