public class Problem21_AdditiveNumber {
    public boolean isAdditiveNumber(String num) {
        int n = num.length();
        for (int i = 1; i <= n/2; i++) for (int j = i+1; j <= n-Math.max(i,j-i); j++) {
            if (num.charAt(0)=='0' && i>1) continue;
            if (num.charAt(i)=='0' && j-i>1) continue;
            if (check(num, Long.parseLong(num.substring(0,i)), Long.parseLong(num.substring(i,j)), j)) return true;
        }
        return false;
    }
    private boolean check(String num, long a, long b, int start) {
        if (start == num.length()) return true;
        long c = a+b; String s = String.valueOf(c);
        if (!num.startsWith(s, start)) return false;
        return check(num, b, c, start+s.length());
    }
    public static void main(String[] args) { System.out.println(new Problem21_AdditiveNumber().isAdditiveNumber("112358")); }
}
