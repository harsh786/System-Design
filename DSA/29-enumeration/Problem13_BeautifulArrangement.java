public class Problem13_BeautifulArrangement {
    int count = 0;
    public int countArrangement(int n) {
        backtrack(n, 1, new boolean[n+1]); return count;
    }
    private void backtrack(int n, int pos, boolean[] used) {
        if (pos > n) { count++; return; }
        for (int i = 1; i <= n; i++) if (!used[i] && (i%pos==0||pos%i==0)) { used[i]=true; backtrack(n,pos+1,used); used[i]=false; }
    }
    public static void main(String[] args) { System.out.println(new Problem13_BeautifulArrangement().countArrangement(6)); }
}
