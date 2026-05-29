package numbertheory;

/**
 * Problem 31: Excel Sheet Column Number (LeetCode 171)
 * 
 * Approach: Base-26 conversion where A=1, B=2, ..., Z=26.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 */
public class Problem31_ExcelSheetColumnNumber {
    
    public int titleToNumber(String columnTitle) {
        int result = 0;
        for (char c : columnTitle.toCharArray()) result = result * 26 + (c - 'A' + 1);
        return result;
    }
    
    public static void main(String[] args) {
        Problem31_ExcelSheetColumnNumber sol = new Problem31_ExcelSheetColumnNumber();
        System.out.println(sol.titleToNumber("A"));   // 1
        System.out.println(sol.titleToNumber("AB"));  // 28
        System.out.println(sol.titleToNumber("ZY"));  // 701
    }
}
