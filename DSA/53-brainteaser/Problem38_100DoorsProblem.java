public class Problem38_100DoorsProblem {
    // 100 doors toggled on pass i for every i-th door. Open doors = perfect squares.
    static void solve(int n) {
        boolean[] doors = new boolean[n + 1];
        for (int i = 1; i <= n; i++)
            for (int j = i; j <= n; j += i) doors[j] = !doors[j];
        System.out.print("Open doors: ");
        for (int i = 1; i <= n; i++) if (doors[i]) System.out.print(i + " ");
        System.out.println();
        System.out.print("Perfect squares: ");
        for (int i = 1; i * i <= n; i++) System.out.print(i * i + " ");
        System.out.println();
    }
    
    public static void main(String[] args) { solve(100); }
}
