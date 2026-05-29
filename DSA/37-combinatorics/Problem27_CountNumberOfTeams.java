public class Problem27_CountNumberOfTeams {
    public int numTeams(int[] rating) {
        int n = rating.length, count = 0;
        for (int j = 1; j < n - 1; j++) {
            int leftSmall = 0, leftBig = 0, rightSmall = 0, rightBig = 0;
            for (int i = 0; i < j; i++) { if (rating[i] < rating[j]) leftSmall++; else if (rating[i] > rating[j]) leftBig++; }
            for (int k = j + 1; k < n; k++) { if (rating[k] < rating[j]) rightSmall++; else if (rating[k] > rating[j]) rightBig++; }
            count += leftSmall * rightBig + leftBig * rightSmall;
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(new Problem27_CountNumberOfTeams().numTeams(new int[]{2,5,3,4,1}));
    }
}
