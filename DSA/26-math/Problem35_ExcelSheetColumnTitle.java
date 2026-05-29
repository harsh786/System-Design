/**
 * Problem 35: Excel Sheet Column Title
 * Convert column number to title: 1->A, 28->AB, 701->ZY.
 *
 * Approach: Base-26 conversion but 1-indexed (subtract 1 before mod).
 * Time Complexity: O(log26(n))
 * Space Complexity: O(1)
 *
 * Production Analogy: Like generating human-readable shard/partition labels
 * from numeric identifiers.
 */
public class Problem35_ExcelSheetColumnTitle {

    public static String convertToTitle(int columnNumber) {
        StringBuilder sb = new StringBuilder();
        while (columnNumber > 0) {
            columnNumber--;
            sb.append((char) ('A' + columnNumber % 26));
            columnNumber /= 26;
        }
        return sb.reverse().toString();
    }

    public static void main(String[] args) {
        System.out.println(convertToTitle(1));    // "A"
        System.out.println(convertToTitle(28));   // "AB"
        System.out.println(convertToTitle(701));  // "ZY"
        System.out.println(convertToTitle(703));  // "AAA"
        System.out.println(convertToTitle(26));   // "Z"
    }
}
