public class Problem41_InvariantChessboardProblem {
    // Domino tiling: 8x8 board with 2 opposite corners removed cannot be tiled with dominoes
    // Proof: removed squares are same color, but each domino covers one black + one white
    static boolean canTile(int n, boolean[][] removed) {
        int black = 0, white = 0;
        for (int i = 0; i < n; i++) for (int j = 0; j < n; j++) {
            if (removed[i][j]) continue;
            if ((i + j) % 2 == 0) white++; else black++;
        }
        return black == white; // necessary condition for domino tiling
    }
    
    public static void main(String[] args) {
        boolean[][] removed = new boolean[8][8];
        removed[0][0] = true; removed[7][7] = true; // same color
        System.out.println("Opposite corners removed: " + canTile(8, removed)); // false
        removed = new boolean[8][8];
        removed[0][0] = true; removed[0][1] = true; // different color
        System.out.println("Adjacent corners removed: " + canTile(8, removed)); // true
    }
}
