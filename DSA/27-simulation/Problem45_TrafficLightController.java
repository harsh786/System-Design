/**
 * Problem: Traffic Light Controller Simulation
 * Approach: State machine with timed transitions
 * Complexity: O(1) per state transition
 * Production Analogy: Finite state machines in embedded systems and workflow engines
 */
public class Problem45_TrafficLightController {
    enum State { GREEN_NS, YELLOW_NS, GREEN_EW, YELLOW_EW }
    State current = State.GREEN_NS;
    int timer = 0;
    static final int GREEN_DUR = 30, YELLOW_DUR = 5;

    public String tick() {
        timer++;
        switch (current) {
            case GREEN_NS: if (timer >= GREEN_DUR) { current = State.YELLOW_NS; timer = 0; } break;
            case YELLOW_NS: if (timer >= YELLOW_DUR) { current = State.GREEN_EW; timer = 0; } break;
            case GREEN_EW: if (timer >= GREEN_DUR) { current = State.YELLOW_EW; timer = 0; } break;
            case YELLOW_EW: if (timer >= YELLOW_DUR) { current = State.GREEN_NS; timer = 0; } break;
        }
        return current.name();
    }

    public static void main(String[] args) {
        Problem45_TrafficLightController ctrl = new Problem45_TrafficLightController();
        for (int i = 0; i < 80; i++) {
            String state = ctrl.tick();
            if (i % 10 == 0) System.out.println("t=" + i + " -> " + state);
        }
    }
}
