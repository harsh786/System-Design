public class Problem09_JosephusProblem {
    // Last person standing when every k-th person is eliminated
    static int josephus(int n, int k) {
        int pos = 0;
        for (int i = 2; i <= n; i++) pos = (pos + k) % i;
        return pos + 1; // 1-indexed
    }
    
    public static void main(String[] args) {
        System.out.println("n=7, k=3: " + josephus(7, 3)); // 4
        System.out.println("n=5, k=2: " + josephus(5, 2)); // 3
    }
}
