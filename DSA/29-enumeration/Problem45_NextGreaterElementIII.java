public class Problem45_NextGreaterElementIII {
    public int nextGreaterElement(int n) {
        char[] digits = String.valueOf(n).toCharArray();
        int len = digits.length, i = len-2;
        while (i >= 0 && digits[i] >= digits[i+1]) i--;
        if (i < 0) return -1;
        int j = len-1;
        while (digits[j] <= digits[i]) j--;
        char tmp = digits[i]; digits[i] = digits[j]; digits[j] = tmp;
        // reverse from i+1
        int lo = i+1, hi = len-1;
        while (lo < hi) { tmp = digits[lo]; digits[lo] = digits[hi]; digits[hi] = tmp; lo++; hi--; }
        long result = Long.parseLong(new String(digits));
        return result > Integer.MAX_VALUE ? -1 : (int) result;
    }
    public static void main(String[] args) { System.out.println(new Problem45_NextGreaterElementIII().nextGreaterElement(12)); }
}
