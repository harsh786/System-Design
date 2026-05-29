/**
 * Problem 16: UTF-8 Validation
 * Validate if integer array represents valid UTF-8 encoding.
 * 
 * Rules: 1-byte: 0xxxxxxx, 2-byte: 110xxxxx 10xxxxxx, etc.
 * Approach: Use bit masks to check leading bits pattern.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Validating incoming byte streams in network protocol parsers.
 */
public class Problem16_UTF8Validation {
    public static boolean validUtf8(int[] data) {
        int remaining = 0; // continuation bytes expected
        for (int d : data) {
            if (remaining > 0) {
                // Must start with 10xxxxxx
                if ((d & 0b11000000) != 0b10000000) return false;
                remaining--;
            } else {
                if ((d & 0b10000000) == 0) remaining = 0;        // 0xxxxxxx
                else if ((d & 0b11100000) == 0b11000000) remaining = 1; // 110xxxxx
                else if ((d & 0b11110000) == 0b11100000) remaining = 2; // 1110xxxx
                else if ((d & 0b11111000) == 0b11110000) remaining = 3; // 11110xxx
                else return false;
            }
        }
        return remaining == 0;
    }

    public static void main(String[] args) {
        System.out.println(validUtf8(new int[]{197, 130, 1})); // true
        System.out.println(validUtf8(new int[]{235, 140, 4})); // false
        System.out.println(validUtf8(new int[]{0})); // true
    }
}
