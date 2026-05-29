import java.util.*;

public class Problem34_RandomizedRoundRobin {
    // Weighted round robin with random start
    String[] servers;
    int[] weights;
    Random rand = new Random();

    public Problem34_RandomizedRoundRobin(String[] servers, int[] weights) {
        this.servers = servers; this.weights = weights;
    }

    public List<String> schedule(int requests) {
        List<String> expanded = new ArrayList<>();
        for (int i = 0; i < servers.length; i++)
            for (int j = 0; j < weights[i]; j++) expanded.add(servers[i]);
        Collections.shuffle(expanded, rand); // randomize initial order
        List<String> result = new ArrayList<>();
        for (int i = 0; i < requests; i++) result.add(expanded.get(i % expanded.size()));
        return result;
    }

    public static void main(String[] args) {
        Problem34_RandomizedRoundRobin rr = new Problem34_RandomizedRoundRobin(
            new String[]{"A","B","C"}, new int[]{3,2,1});
        System.out.println(rr.schedule(12));
    }
}
