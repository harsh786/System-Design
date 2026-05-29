import java.util.*;

/**
 * Problem 7: Reservoir Sampling for A/B Testing
 * 
 * In A/B testing, we need to randomly assign users to groups as they arrive.
 * Reservoir sampling helps when:
 * - We don't know total user count upfront
 * - We need exactly k users in the treatment group
 * - Users arrive as a stream (real-time)
 * - We need a representative sample for analysis
 * 
 * This implements a streaming A/B test assignment system.
 */
public class Problem07_ReservoirSamplingABTesting {

    static class User {
        int id;
        String segment; // "new", "returning", "premium"
        long timestamp;
        
        User(int id, String segment, long timestamp) {
            this.id = id;
            this.segment = segment;
            this.timestamp = timestamp;
        }
    }

    static class ABTestAssigner {
        private int treatmentSize;       // Desired treatment group size
        private List<User> treatment;    // Reservoir for treatment group
        private int totalSeen;
        private Random rand;

        ABTestAssigner(int treatmentSize) {
            this.treatmentSize = treatmentSize;
            this.treatment = new ArrayList<>();
            this.totalSeen = 0;
            this.rand = new Random(42);
        }

        /** Process a new user arrival. Returns true if assigned to treatment. */
        public boolean processUser(User user) {
            totalSeen++;
            
            if (treatment.size() < treatmentSize) {
                treatment.add(user);
                return true;
            } else {
                int j = rand.nextInt(totalSeen);
                if (j < treatmentSize) {
                    treatment.set(j, user);
                    return true;
                }
                return false;
            }
        }

        public List<User> getTreatmentGroup() { return treatment; }
        public int getTotalSeen() { return totalSeen; }
    }

    public static void main(String[] args) {
        int treatmentSize = 100;
        ABTestAssigner assigner = new ABTestAssigner(treatmentSize);
        
        Random rand = new Random(42);
        String[] segments = {"new", "returning", "premium"};
        double[] segmentProbs = {0.5, 0.35, 0.15};
        int totalUsers = 10000;
        
        // Simulate user stream
        Map<String, Integer> totalBySegment = new HashMap<>();
        for (int i = 0; i < totalUsers; i++) {
            double r = rand.nextDouble();
            String seg = r < segmentProbs[0] ? segments[0] : 
                         r < segmentProbs[0] + segmentProbs[1] ? segments[1] : segments[2];
            totalBySegment.merge(seg, 1, Integer::sum);
            assigner.processUser(new User(i, seg, System.currentTimeMillis()));
        }
        
        // Analyze treatment group composition
        Map<String, Integer> treatmentBySegment = new HashMap<>();
        for (User u : assigner.getTreatmentGroup()) {
            treatmentBySegment.merge(u.segment, 1, Integer::sum);
        }
        
        System.out.println("A/B Testing with Reservoir Sampling");
        System.out.printf("Total users: %d, Treatment group: %d%n%n", totalUsers, treatmentSize);
        
        System.out.printf("%-12s %-12s %-12s %-12s%n", "Segment", "Population%", "Treatment%", "Bias?");
        for (String seg : segments) {
            double popPct = 100.0 * totalBySegment.getOrDefault(seg, 0) / totalUsers;
            double treatPct = 100.0 * treatmentBySegment.getOrDefault(seg, 0) / treatmentSize;
            String bias = Math.abs(popPct - treatPct) > 5 ? "YES" : "no";
            System.out.printf("%-12s %-12.1f %-12.1f %-12s%n", seg, popPct, treatPct, bias);
        }
        
        System.out.println("\nReservoir sampling ensures representative treatment group.");
    }
}
