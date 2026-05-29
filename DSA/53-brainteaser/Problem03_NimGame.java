public class Problem03_NimGame {
    // You win if n is not divisible by 4 (take 1-3 stones)
    static boolean canWin(int n) { return n % 4 != 0; }
    
    public static void main(String[] args) {
        for (int i = 1; i <= 10; i++)
            System.out.println("n=" + i + " win=" + canWin(i));
    }
}
