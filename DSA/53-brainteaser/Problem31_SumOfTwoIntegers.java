public class Problem31_SumOfTwoIntegers {
    static int getSum(int a, int b) {
        while (b != 0) { int carry = (a & b) << 1; a = a ^ b; b = carry; }
        return a;
    }
    
    static int subtract(int a, int b) { return getSum(a, getSum(~b, 1)); }
    
    public static void main(String[] args) {
        System.out.println("5+3=" + getSum(5, 3));
        System.out.println("7-2=" + subtract(7, 2));
    }
}
