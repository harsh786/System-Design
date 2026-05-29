public class Problem46_TwoSumWithoutAddition {
    // Add using bit manipulation
    static int add(int a, int b) {
        while (b != 0) { int c = (a & b) << 1; a ^= b; b = c; }
        return a;
    }
    
    static int negate(int a) { return add(~a, 1); }
    static int subtract(int a, int b) { return add(a, negate(b)); }
    
    public static void main(String[] args) {
        System.out.println("15+7=" + add(15, 7));
        System.out.println("15-7=" + subtract(15, 7));
    }
}
