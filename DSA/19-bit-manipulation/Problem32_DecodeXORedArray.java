/**
 * Problem 32: Decode XORed Array
 * encoded[i] = arr[i] ^ arr[i+1]. Given first element, decode.
 * 
 * Approach: arr[i+1] = encoded[i] ^ arr[i]
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Reconstructing original message from differential XOR encoding.
 */
public class Problem32_DecodeXORedArray {
    public static int[] decode(int[] encoded, int first) {
        int[] arr = new int[encoded.length + 1];
        arr[0] = first;
        for (int i = 0; i < encoded.length; i++) {
            arr[i + 1] = encoded[i] ^ arr[i];
        }
        return arr;
    }

    public static void main(String[] args) {
        int[] r = decode(new int[]{1, 2, 3}, 1);
        for (int v : r) System.out.print(v + " "); // 1 0 2 1
        System.out.println();
        r = decode(new int[]{6, 2, 7, 3}, 4);
        for (int v : r) System.out.print(v + " "); // 4 2 0 7 4
        System.out.println();
    }
}
