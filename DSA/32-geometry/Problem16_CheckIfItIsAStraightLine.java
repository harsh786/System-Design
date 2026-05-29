public class Problem16_CheckIfItIsAStraightLine {
    public static boolean checkStraightLine(int[][] coordinates) {
        int dx = coordinates[1][0] - coordinates[0][0], dy = coordinates[1][1] - coordinates[0][1];
        for (int i = 2; i < coordinates.length; i++) {
            int dx2 = coordinates[i][0] - coordinates[0][0], dy2 = coordinates[i][1] - coordinates[0][1];
            if (dx * dy2 != dy * dx2) return false;
        }
        return true;
    }
    public static void main(String[] args) {
        System.out.println(checkStraightLine(new int[][]{{1,2},{2,3},{3,4},{4,5}})); // true
    }
}
