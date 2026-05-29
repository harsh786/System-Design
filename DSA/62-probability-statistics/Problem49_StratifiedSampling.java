import java.util.*;

public class Problem49_StratifiedSampling {
    public List<Integer> stratifiedSample(int[][] strata, int totalSamples) {
        Random rand = new Random();
        int totalPop = 0;
        for (int[] s : strata) totalPop += s.length;
        List<Integer> result = new ArrayList<>();
        for (int[] stratum : strata) {
            int n = (int)Math.round((double)stratum.length / totalPop * totalSamples);
            List<Integer> pool = new ArrayList<>();
            for (int v : stratum) pool.add(v);
            Collections.shuffle(pool, rand);
            for (int i = 0; i < Math.min(n, pool.size()); i++) result.add(pool.get(i));
        }
        return result;
    }

    public static void main(String[] args) {
        Problem49_StratifiedSampling sol = new Problem49_StratifiedSampling();
        int[][] strata = {{1,2,3,4,5}, {10,20,30,40,50,60,70,80,90,100}, {200,300,400}};
        System.out.println(sol.stratifiedSample(strata, 6));
    }
}
