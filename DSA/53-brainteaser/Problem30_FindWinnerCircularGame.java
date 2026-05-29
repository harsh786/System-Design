public class Problem30_FindWinnerCircularGame {
    // LC 1823 - Josephus problem
    static int findTheWinner(int n, int k) {
        int pos = 0;
        for (int i = 2; i <= n; i++) pos = (pos + k) % i;
        return pos + 1;
    }
    
    public static void main(String[] args) {
        System.out.println("n=5,k=2: " + findTheWinner(5, 2)); // 3
        System.out.println("n=6,k=5: " + findTheWinner(6, 5)); // 1
    }
}
