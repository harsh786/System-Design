import java.util.*;

public class Problem48_DLLForSlidingWindow {
    // Monotonic deque using DLL for sliding window max
    static class Node{int val,idx;Node prev,next;Node(int v,int i){val=v;idx=i;}}
    Node head=new Node(0,0),tail=new Node(0,0);
    
    Problem48_DLLForSlidingWindow(){head.next=tail;tail.prev=head;}
    void pushBack(int val,int idx){
        Node n=new Node(val,idx);
        while(tail.prev!=head&&tail.prev.val<=val){Node rm=tail.prev;rm.prev.next=tail;tail.prev=rm.prev;}
        n.prev=tail.prev;n.next=tail;tail.prev.next=n;tail.prev=n;
    }
    void popFront(int idx){if(head.next!=tail&&head.next.idx<=idx){Node rm=head.next;head.next=rm.next;rm.next.prev=head;}}
    int peekFront(){return head.next.val;}
    
    static int[] maxSlidingWindow(int[] nums, int k) {
        Problem48_DLLForSlidingWindow dq=new Problem48_DLLForSlidingWindow();
        int[] result=new int[nums.length-k+1];
        for(int i=0;i<nums.length;i++){
            dq.pushBack(nums[i],i);
            dq.popFront(i-k);
            if(i>=k-1)result[i-k+1]=dq.peekFront();
        }
        return result;
    }
    
    public static void main(String[] args) {
        System.out.println(Arrays.toString(maxSlidingWindow(new int[]{1,3,-1,-3,5,3,6,7},3)));
        // [3,3,5,5,6,7]
    }
}
