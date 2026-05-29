import java.util.*;

public class Problem46_LateEventHandling {
    // Late Event Handling strategies: Drop, Update, Side-output.
    
    enum Strategy { DROP, UPDATE, SIDE_OUTPUT }
    
    Map<Long, Integer> windowResults = new HashMap<>(); // windowId -> aggregate
    long watermark = 0;
    long windowSize = 5000;
    List<String> sideOutput = new ArrayList<>();
    
    public String processEvent(long eventTime, int value, Strategy strategy) {
        long windowId = eventTime / windowSize * windowSize;
        watermark = Math.max(watermark, eventTime);
        
        boolean isLate = windowId + windowSize < watermark;
        
        if (!isLate) {
            windowResults.merge(windowId, value, Integer::sum);
            return "PROCESSED: window=" + windowId;
        }
        
        switch (strategy) {
            case DROP: return "DROPPED late event at " + eventTime;
            case UPDATE:
                windowResults.merge(windowId, value, Integer::sum);
                return "UPDATED window=" + windowId + " (late)";
            case SIDE_OUTPUT:
                String msg = "LATE: eventTime=" + eventTime + ", value=" + value;
                sideOutput.add(msg);
                return msg;
            default: return "UNKNOWN";
        }
    }
    
    public static void main(String[] args) {
        Problem46_LateEventHandling sol = new Problem46_LateEventHandling();
        System.out.println(sol.processEvent(1000, 5, Strategy.UPDATE));
        System.out.println(sol.processEvent(6000, 3, Strategy.UPDATE));
        System.out.println(sol.processEvent(12000, 7, Strategy.UPDATE));
        // Now event at 2000 is late (watermark at 12000)
        System.out.println(sol.processEvent(2000, 1, Strategy.DROP));
        System.out.println(sol.processEvent(2000, 1, Strategy.UPDATE));
        System.out.println(sol.processEvent(2000, 1, Strategy.SIDE_OUTPUT));
    }
}
