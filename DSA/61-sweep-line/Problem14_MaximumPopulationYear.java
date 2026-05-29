import java.util.*;

public class Problem14_MaximumPopulationYear {
    public int maximumPopulation(int[][] logs) {
        int[] diff = new int[101]; // 1950-2050
        for (int[] l : logs) { diff[l[0] - 1950]++; diff[l[1] - 1950]--; }
        int max = 0, cur = 0, year = 1950;
        for (int i = 0; i < 101; i++) { cur += diff[i]; if (cur > max) { max = cur; year = 1950 + i; } }
        return year;
    }

    public static void main(String[] args) {
        Problem14_MaximumPopulationYear sol = new Problem14_MaximumPopulationYear();
        System.out.println(sol.maximumPopulation(new int[][]{{1993,1999},{2000,2010}})); // 1993
    }
}
