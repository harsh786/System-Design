/**
 * Problem 9: Excel Sheet Column Number
 * Convert Excel column title to number: A->1, B->2, ..., Z->26, AA->27.
 *
 * Approach: Base-26 number system conversion.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 *
 * Production Analogy: Like parsing base-N encoded identifiers in URL shorteners
 * or database shard key generation.
 */
public class Problem09_ExcelSheetColumnNumber {

    public static int titleToNumber(String columnTitle) {
        int result = 0;
        for (char c : columnTitle.toCharArray()) {
            result = result * 26 + (c - 'A' + 1);
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(titleToNumber("A"));    // 1
        System.out.println(titleToNumber("AB"));   // 28
        System.out.println(titleToNumber("ZY"));   // 701
        System.out.println(titleToNumber("AAA"));  // 703
    }
}
