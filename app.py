@app.route("/api/data", methods=["GET"])
def get_data():
    try:
        month = request.args.get("month", default=datetime.now().month, type=int)
        year = request.args.get("year", default=datetime.now().year, type=int)
        pilots = Pilot.query.filter(Pilot.name.notin_(PILOTOS_EXCLUIDOS)).all()
        logs_current = FlightLog.query.filter_by(month=month, year=year).all()

        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        logs_prev = FlightLog.query.filter_by(month=prev_month, year=prev_year).all()
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1
        logs_next = FlightLog.query.filter_by(month=next_month, year=next_year).all()

        logs_current_map = logs_por_piloto(logs_current)
        logs_prev_map = logs_por_piloto(logs_prev)
        logs_next_map = logs_por_piloto(logs_next)

        logs_adjacent = {}
        for pilot_name in set(logs_current_map) | set(logs_prev_map) | set(logs_next_map):
            logs_adjacent[pilot_name] = {}
            for key, horas in logs_prev_map.get(pilot_name, {}).items():
                logs_adjacent[pilot_name][key] = horas
            for key, horas in logs_current_map.get(pilot_name, {}).items():
                logs_adjacent[pilot_name][key] = horas
            for key, horas in logs_next_map.get(pilot_name, {}).items():
                logs_adjacent[pilot_name][key] = horas

        sugestoes_consolidadas = {}
        for log in logs_current:
            if log.sugestoes:
                sugestoes_consolidadas.update(log.sugestoes)

        # === NOVO: carregar status (cores) ===
        overrides = StatusOverride.query.filter_by(month=month, year=year).all()
        status_map = {}
        for ov in overrides:
            if ov.pilot.name not in status_map:
                status_map[ov.pilot.name] = {}
            status_map[ov.pilot.name][ov.day] = ov.status
        # ====================================

        result = {
            "pilots": [{"name": p.name, "group": p.group, "full_name": p.full_name or p.name} for p in pilots],
            "logs": {},
            "logs_adjacent": logs_adjacent,
            "escala": {},
            "sugestoes": sugestoes_consolidadas,
            "status": status_map          # ← cores voltam agora
        }

        for log in logs_current:
            if log.pilot.name not in result["logs"]:
                result["logs"][log.pilot.name] = {}
            result["logs"][log.pilot.name][log.day] = log.hours

        for p in pilots:
            escala_pilot = obtener_escala_dinamica(p, month, year)
            if escala_pilot:
                result["escala"][p.name] = escala_pilot

        print(f"📤 Retornando {len(sugestoes_consolidadas)} sugestões e {len(status_map)} status para {month}/{year}")
        return jsonify(result)
    except Exception as e:
        print(f"❌ Erro em /api/data (GET): {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
