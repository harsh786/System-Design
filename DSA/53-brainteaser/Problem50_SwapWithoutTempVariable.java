public class Problem50_SwapWithoutTempVariable {
    static void xorSwap(int[] arr, int i, int j) {
        if (i == j) return;
        arr[i] ^= arr[j]; arr[j] ^= arr[i]; arr[i] ^= arr[j];
    }
    
    static void arithmeticSwap(int[] arr, int i, int j) {
        arr[i] = arr[i] + arr[j]; arr[j] = arr[i] - arr[j]; arr[i] = arr[i] - arr[j];
    }
    
    public static void main(String[] args) {
        int[] a = {5, 10};
        System.out.println("Before: " + java.util.Arrays.toString(a));
        xorSwap(a, 0, 1);
        System.out.println("After XOR swap: " + java.util.Arrays.toString(a));
        arithmeticSwap(a, 0, 1);
        System.out.println("After arithmetic swap: " + java.util.Arrays.toString(a));
    }
}
