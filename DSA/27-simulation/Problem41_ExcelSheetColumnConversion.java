/**
 * Problem: Excel Sheet Column Title/Number (LeetCode 168/171)
 * Approach: Base-26 conversion simulation
 * Complexity: O(log n) time, O(1) space
 * Production Analogy: Encoding/decoding between numbering systems in data formats
 */
public class Problem41_ExcelSheetColumnConversion {
    public String convertToTitle(int columnNumber) {
        StringBuilder sb = new StringBuilder();
        while (columnNumber > 0) {
            columnNumber--;
            sb.insert(0, (char)('A' + columnNumber % 26));
            columnNumber /= 26;
        }
        return sb.toString();
    }
    public int titleToNumber(String columnTitle) {
        int result = 0;
        for (char c : columnTitle.toCharArray()) result = result * 26 + (c - 'A' + 1);
        return result;
    }
    public static void main(String[] args) {
        Problem41_ExcelSheetColumnConversion sol = new Problem41_ExcelSheetColumnConversion();
        System.out.println(sol.convertToTitle(28)); // AB
        System.out.println(sol.titleToNumber("AB")); // 28
    }
}
