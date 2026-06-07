package com.codex.javaconcepts.lld;

import java.util.ArrayDeque;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.Queue;
import java.util.UUID;

public class MiniParkingLotExample {
    public static void main(String[] args) {
        ParkingLot lot = new ParkingLot();
        lot.addSpot(new ParkingSpot("S1", VehicleType.CAR));
        lot.addSpot(new ParkingSpot("S2", VehicleType.BIKE));

        Ticket ticket = lot.park(new Vehicle("KA-01-1234", VehicleType.CAR));
        System.out.println("Parked ticket: " + ticket);

        Optional<Ticket> activeTicket = lot.findActiveTicket(ticket.id());
        System.out.println("Active ticket found: " + activeTicket.isPresent());

        lot.unpark(ticket.id());
        System.out.println("Active ticket after unpark: " + lot.findActiveTicket(ticket.id()).isPresent());
    }

    private static class ParkingLot {
        private final EnumMap<VehicleType, Queue<ParkingSpot>> availableByType =
            new EnumMap<>(VehicleType.class);
        private final Map<String, ParkingSpot> spotsById = new HashMap<>();
        private final Map<String, Ticket> activeTickets = new HashMap<>();

        private ParkingLot() {
            for (VehicleType type : VehicleType.values()) {
                availableByType.put(type, new ArrayDeque<>());
            }
        }

        void addSpot(ParkingSpot spot) {
            spotsById.put(spot.id(), spot);
            availableByType.get(spot.type()).offer(spot);
        }

        Ticket park(Vehicle vehicle) {
            Queue<ParkingSpot> available = availableByType.get(vehicle.type());
            ParkingSpot spot = available.poll();
            if (spot == null) {
                throw new NoSpotAvailableException(vehicle.type());
            }

            Ticket ticket = new Ticket(UUID.randomUUID().toString(), vehicle, spot);
            activeTickets.put(ticket.id(), ticket);
            return ticket;
        }

        void unpark(String ticketId) {
            Ticket ticket = activeTickets.remove(ticketId);
            if (ticket == null) {
                throw new IllegalArgumentException("unknown ticket: " + ticketId);
            }
            availableByType.get(ticket.spot().type()).offer(ticket.spot());
        }

        Optional<Ticket> findActiveTicket(String ticketId) {
            return Optional.ofNullable(activeTickets.get(ticketId));
        }
    }

    private enum VehicleType {
        BIKE, CAR
    }

    private record Vehicle(String numberPlate, VehicleType type) {
    }

    private record ParkingSpot(String id, VehicleType type) {
    }

    private record Ticket(String id, Vehicle vehicle, ParkingSpot spot) {
    }

    private static class NoSpotAvailableException extends RuntimeException {
        private NoSpotAvailableException(VehicleType type) {
            super("no spot available for " + type);
        }
    }
}

